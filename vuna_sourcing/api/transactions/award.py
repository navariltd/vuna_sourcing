# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt, format_datetime, getdate, now_datetime, today

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.bidding import (
	AWARDED,
	NOT_AWARDED,
	OUTCOME_AWARDED,
	OUTCOME_NOT_SELECTED,
	PENDING_SELECTION,
	SEALED_BID,
	closes_at,
	closing_passed,
)
from vuna_sourcing.api.transactions.supplier import (
	PURCHASE_ORDER,
	RECEIVED,
	RFQ,
	RFQ_ITEM,
	RFQ_SUPPLIER,
	SUPPLIER_QUOTATION,
	SUPPLIER_QUOTATION_ITEM,
)

AWARD = "RFQ Award"
SETTINGS = "Sourcing Settings"


def ranked_quotes(request: str) -> list[dict]:
	quotation = frappe.qb.DocType(SUPPLIER_QUOTATION)
	item = frappe.qb.DocType(SUPPLIER_QUOTATION_ITEM)
	quotes = (
		frappe.qb.from_(item)
		.join(quotation)
		.on(quotation.name == item.parent)
		.select(
			quotation.name.as_("supplier_quotation"),
			quotation.supplier,
			quotation.supplier_name,
			quotation.currency,
			quotation.creation,
			Sum(item.amount).as_("total"),
			Sum(item.base_amount).as_("base_total"),
		)
		.where(item.request_for_quotation == request)
		.where(quotation.docstatus == 1)
		.groupby(
			quotation.name,
			quotation.supplier,
			quotation.supplier_name,
			quotation.currency,
			quotation.creation,
		)
	).run(as_dict=True)

	quotes.sort(key=lambda quote: (flt(quote.base_total), quote.creation))
	lowest = flt(quotes[0].base_total) if quotes else None
	for rank, quote in enumerate(quotes, start=1):
		quote.rank = rank
		quote.is_lowest = flt(quote.base_total) == lowest
	return quotes


def award_blockers(request) -> list[str]:
	blockers = []
	if request.docstatus != 1:
		blockers.append(_("Submit {0} before awarding it.").format(request.name))

	if not closing_passed(request):
		closing = closes_at(request)
		blockers.append(
			_("Bids close at {0}.").format(format_datetime(closing))
			if closing
			else _("Set when bids close before awarding.")
		)

	if request.get("bidding_method") == SEALED_BID and not cint(request.get("quotes_opened")):
		blockers.append(_("The opening committee has not opened the quotations yet."))

	if not ranked_quotes(request.name):
		blockers.append(_("No supplier quotation for this request has been submitted yet."))

	return blockers


def submitted_award(request: str) -> dict | None:
	return frappe.db.get_value(
		AWARD,
		{"request_for_quotation": request, "docstatus": 1},
		["name", "supplier", "supplier_quotation"],
		as_dict=True,
	)


def refresh_award_status(name: str) -> str | None:
	request = frappe.get_doc(RFQ, name)
	award = submitted_award(name)

	if award:
		status = AWARDED
	elif request.award_status == NOT_AWARDED:
		status = NOT_AWARDED
	elif request.docstatus == 1 and not award_blockers(request):
		status = PENDING_SELECTION
	else:
		status = None

	request.db_set("award_status", status, update_modified=False)
	set_outcomes(request, award, decided=status in (AWARDED, NOT_AWARDED))
	return status


def set_outcomes(request, award: dict | None, decided: bool) -> None:
	quotes = ranked_quotes(request.name)
	quoted = {quote.supplier for quote in quotes} | {
		row.supplier for row in request.suppliers if row.quote_status == RECEIVED
	}

	def outcome(won: bool) -> str | None:
		if not decided:
			return None
		return OUTCOME_AWARDED if won else OUTCOME_NOT_SELECTED

	for row in request.suppliers:
		value = outcome(bool(award) and row.supplier == award.supplier) if row.supplier in quoted else None
		frappe.db.set_value(RFQ_SUPPLIER, row.name, "award_outcome", value, update_modified=False)

	for quote in quotes:
		won = bool(award) and quote.supplier_quotation == award.supplier_quotation
		frappe.db.set_value(
			SUPPLIER_QUOTATION, quote.supplier_quotation, "award_outcome", outcome(won), update_modified=False
		)


def requests_of(quote) -> list[str]:
	return list({row.request_for_quotation for row in quote.get("items") if row.request_for_quotation})


def refresh_for_quotation(doc, method: str | None = None) -> None:
	for request in requests_of(doc):
		refresh_award_status(request)


def refresh_pending_selection() -> None:
	for name in frappe.get_all(
		RFQ,
		filters={"docstatus": 1, "award_status": ("is", "not set"), "bid_closing": ("<=", now_datetime())},
		pluck="name",
	):
		refresh_award_status(name)


def recipients_of(request: str, supplier: str) -> list[str]:
	listed = frappe.db.get_value(RFQ_SUPPLIER, {"parent": request, "supplier": supplier}, "email_id")
	users = frappe.get_all(
		"Portal User", filters={"parenttype": "Supplier", "parent": supplier}, pluck="user"
	)
	emails = frappe.get_all("User", filters={"name": ("in", users or [""]), "enabled": 1}, pluck="email")
	return sorted({email for email in [listed, *emails] if email})


def notify_supplier(request: str, supplier: str, subject: str, message: str) -> None:
	recipients = recipients_of(request, supplier)
	if not recipients:
		return

	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype=RFQ,
			reference_name=request,
		)
	except Exception:
		frappe.log_error("RFQ award notification failed")


def notify_outcomes(request: str) -> None:
	for row in frappe.get_all(
		RFQ_SUPPLIER,
		filters={"parent": request, "parenttype": RFQ, "award_outcome": ("is", "set")},
		fields=["supplier", "award_outcome"],
	):
		if row.award_outcome == OUTCOME_AWARDED:
			notify_supplier(
				request,
				row.supplier,
				_("Awarded: {0}").format(request),
				_(
					"Your quotation for {0} has been selected. Our team will be in touch with the purchase order."
				).format(request),
			)
		else:
			notify_supplier(
				request,
				row.supplier,
				_("Outcome of {0}").format(request),
				_("Thank you for your quotation for {0}. On this occasion it was not selected.").format(
					request
				),
			)


def notify_withdrawn(request: str, suppliers: list[str]) -> None:
	for supplier in suppliers:
		notify_supplier(
			request,
			supplier,
			_("Award withdrawn: {0}").format(request),
			_(
				"The award for {0} has been withdrawn while we review it. We will let you know the outcome."
			).format(request),
		)


def decided_suppliers(request: str) -> list[str]:
	return frappe.get_all(
		RFQ_SUPPLIER,
		filters={"parent": request, "parenttype": RFQ, "award_outcome": ("is", "set")},
		pluck="supplier",
	)


def live_orders_of(award: str) -> list[str]:
	return orders_of(award, docstatus=0) + orders_of(award, docstatus=1)


def orders_of(award: str, docstatus: int) -> list[str]:
	return frappe.get_all(PURCHASE_ORDER, filters={"rfq_award": award, "docstatus": docstatus}, pluck="name")


def required_by_dates(request: str, lines: list) -> dict:
	rfq_dates = dict(
		frappe.get_all(RFQ_ITEM, filters={"parent": request}, fields=["name", "schedule_date"], as_list=True)
	)
	fallback = frappe.db.get_value(RFQ, request, "schedule_date")
	earliest = getdate(today())

	return {
		line.name: max(
			getdate(
				line.expected_delivery_date
				or rfq_dates.get(line.request_for_quotation_item)
				or fallback
				or earliest
			),
			earliest,
		)
		for line in lines
	}


def make_award_purchase_order(award) -> str:
	from erpnext.buying.doctype.supplier_quotation.supplier_quotation import make_purchase_order

	lines = frappe.get_all(
		SUPPLIER_QUOTATION_ITEM,
		filters={"parent": award.supplier_quotation, "request_for_quotation": award.request_for_quotation},
		fields=["name", "expected_delivery_date", "request_for_quotation_item"],
	)
	required_by = required_by_dates(award.request_for_quotation, lines)

	order = make_purchase_order(
		award.supplier_quotation, args={"filtered_children": [line.name for line in lines]}
	)
	order.rfq_award = award.name
	for row in order.items:
		row.schedule_date = required_by[row.supplier_quotation_item]
	order.schedule_date = min(row.schedule_date for row in order.items)
	order.insert()
	return order.name


def creates_orders_on_award() -> bool:
	return bool(cint(frappe.db.get_single_value(SETTINGS, "create_purchase_orders_on_award")))


def award_overview(request) -> dict:
	return {
		"award_status": request.get("award_status"),
		"blockers": award_blockers(request),
		"award": submitted_award(request.name),
		"quotes": [
			{
				"supplier_quotation": quote.supplier_quotation,
				"supplier": quote.supplier,
				"supplier_name": quote.supplier_name,
				"currency": quote.currency,
				"total": quote.total,
				"base_total": quote.base_total,
				"rank": quote.rank,
				"is_lowest": quote.is_lowest,
			}
			for quote in ranked_quotes(request.name)
		],
	}


def staff_request(name: str):
	frappe.has_permission(AWARD, "read", throw=True)
	request = frappe.get_doc(RFQ, name)
	request.check_permission("read")
	return request


@frappe.whitelist()
def get_award_overview(name: str) -> ApiResponse[dict]:
	return ApiResponse.success(data=award_overview(staff_request(name)))


@frappe.whitelist(methods=["POST"])
def close_without_award(name: str, reason: str) -> ApiResponse[dict]:
	frappe.has_permission(AWARD, "submit", throw=True)
	request = staff_request(name)

	if not (reason or "").strip():
		frappe.throw(_("Give a reason for closing {0} without an award.").format(name))

	if refresh_award_status(name) != PENDING_SELECTION:
		frappe.throw(
			_("Only a request pending selection can be closed without an award."),
			title=_("Cannot close {0}").format(name),
		)

	request.db_set({"award_status": NOT_AWARDED, "award_remarks": reason.strip()}, update_modified=False)
	request.add_comment("Comment", _("Closed without an award: {0}").format(reason.strip()))
	refresh_award_status(name)
	notify_outcomes(name)

	request.reload()
	return ApiResponse.success(_("{0} was closed without an award.").format(name), award_overview(request))
