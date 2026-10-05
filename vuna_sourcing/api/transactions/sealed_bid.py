# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.form.assign_to import add as assign
from frappe.query_builder.functions import IfNull
from frappe.utils import (
	cint,
	format_datetime,
	get_fullname,
	get_system_timezone,
	getdate,
	now_datetime,
)

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.bidding import SEALED_BID, closes_at, closing_passed, is_sealed
from vuna_sourcing.api.transactions.supplier import (
	NO_QUOTE,
	QUOTE_PENDING,
	RFQ,
	RFQ_SUPPLIER,
	SUBMISSION_STATUS_FIELD,
	SUPPLIER_QUOTATION,
	SUPPLIER_QUOTATION_ITEM,
)

COMMITTEE = "RFQ Opening Committee"
COMMITTEE_MEMBER = "RFQ Opening Committee Member"
SETTINGS = "Sourcing Settings"


def sealed_quotes_condition() -> str:
	"""SQL condition that keeps a Supplier Quotation out of desk lists while its RFQ is still sealed.

	A quotation is sealed when any of its items answers a Request for Quotation whose bidding method
	is Sealed Bid and whose quotations have not been opened by the committee yet. The condition is
	appended to the Supplier Quotation list query through `permission_query_conditions`, so it refers
	to the outer table as `tabSupplier Quotation`.
	"""
	quotation = frappe.qb.DocType(SUPPLIER_QUOTATION)
	item = frappe.qb.DocType(SUPPLIER_QUOTATION_ITEM).as_("sealed_item")
	request = frappe.qb.DocType(RFQ).as_("sealed_request")

	sealed_items = (
		frappe.qb.from_(item)
		.join(request)
		.on(request.name == item.request_for_quotation)
		.select(item.name)
		.where(item.parent == quotation.name)
		.where(request.bidding_method == SEALED_BID)
		.where(IfNull(request.quotes_opened, 0) == 0)
	)
	return f"not exists ({sealed_items.get_sql()})"


def sealed_request_of(quote) -> str | None:
	requests = list({row.request_for_quotation for row in quote.get("items") if row.request_for_quotation})
	if not requests:
		return None

	sealed = frappe.get_all(
		RFQ,
		filters={"name": ("in", requests), "bidding_method": SEALED_BID, "quotes_opened": 0},
		pluck="name",
		limit=1,
	)
	return sealed[0] if sealed else None


def committee_members(committee: str | None) -> list[str]:
	if not committee:
		return []

	return frappe.get_all(
		COMMITTEE_MEMBER, filters={"parent": committee, "parenttype": COMMITTEE}, pluck="user"
	)


def received_quotes(request: str) -> int:
	parents = frappe.get_all(
		SUPPLIER_QUOTATION_ITEM, filters={"request_for_quotation": request}, pluck="parent", distinct=True
	)
	if not parents:
		return 0

	statuses = frappe.get_all(
		SUPPLIER_QUOTATION,
		filters={"name": ("in", parents), "docstatus": ("<", 2)},
		pluck=SUBMISSION_STATUS_FIELD,
	)
	return sum(1 for status in statuses if status != QUOTE_PENDING)


def declined_quotes(request: str) -> int:
	return frappe.db.count(RFQ_SUPPLIER, {"parent": request, "parenttype": RFQ, "quote_status": NO_QUOTE})


def assign_committee(request) -> None:
	members = committee_members(request.opening_committee)
	if not members:
		return

	assign(
		{
			"assign_to": members,
			"doctype": RFQ,
			"name": request.name,
			"date": getdate(request.bid_closing),
			"priority": "High",
			"description": _("Open the sealed quotations for {0} once bids close at {1}.").format(
				request.name, format_datetime(request.bid_closing)
			),
		}
	)


def close_opening_tasks(request: str, user: str | None = None) -> None:
	filters = {"reference_type": RFQ, "reference_name": request, "status": "Open"}
	if user:
		filters["allocated_to"] = user

	for task in frappe.get_all("ToDo", filters=filters, pluck="name"):
		frappe.db.set_value("ToDo", task, "status", "Closed")


def sealed_request(name: str):
	request = frappe.get_doc(RFQ, name)
	request.check_permission("read")

	if request.bidding_method != SEALED_BID:
		frappe.throw(_("{0} is not a sealed bid.").format(name))

	return request


def awaiting_confirmation(request) -> list[str]:
	confirmed = {row.member for row in request.opening_confirmations}
	return [member for member in committee_members(request.opening_committee) if member not in confirmed]


def opening_exceptions() -> dict[str, bool]:
	return {
		field: bool(cint(frappe.db.get_single_value(SETTINGS, field)))
		for field in (
			"allow_opening_before_bids_close",
			"allow_opening_below_minimum",
			"allow_any_member_to_open",
		)
	}


def opening_conditions(request) -> list[dict]:
	exceptions = opening_exceptions()
	closing = closes_at(request)
	closing_text = f"{format_datetime(closing)} ({get_system_timezone()})"
	passed = closing_passed(request)
	received = received_quotes(request.name)
	declined = declined_quotes(request.name)
	expected = cint(request.minimum_expected_quotes)

	quotations = _("{0} received").format(received)
	if declined:
		quotations += ", " + _("{0} declined").format(declined)
	quotations += ", " + _("{0} required").format(expected)
	members = committee_members(request.opening_committee)
	waiting = awaiting_confirmation(request)
	confirmed = len(members) - len(waiting)
	any_member = exceptions["allow_any_member_to_open"]

	confirmations = _("{0} of {1} confirmed").format(confirmed, len(members))
	if waiting and not (any_member and confirmed):
		confirmations += ". " + _("Waiting for {0}").format(
			", ".join(get_fullname(member) for member in waiting)
		)

	return [
		{
			"key": "bids_closed",
			"label": _("Bids closed"),
			"required": not exceptions["allow_opening_before_bids_close"],
			"met": passed,
			"detail": _("Closed at {0}").format(closing_text)
			if passed
			else _("Closes at {0}").format(closing_text),
			"prefix": _("Closed at") if passed else _("Closes at"),
			"at": closing,
		},
		{
			"key": "minimum_quotations",
			"label": _("Minimum quotations received"),
			"required": not exceptions["allow_opening_below_minimum"],
			"met": received >= expected,
			"detail": quotations,
		},
		{
			"key": "committee_confirmed",
			"label": _("A committee member confirmed")
			if any_member
			else _("Every committee member confirmed"),
			"required": True,
			"met": confirmed >= 1 if any_member else not waiting,
			"detail": confirmations,
		},
	]


def unmet(conditions: list[dict], *keys: str) -> list[dict]:
	return [
		condition
		for condition in conditions
		if condition["key"] in keys and condition["required"] and not condition["met"]
	]


def opening_status(request, user: str) -> dict:
	members = committee_members(request.opening_committee)
	waiting = awaiting_confirmation(request)
	opened = bool(cint(request.quotes_opened))
	conditions = opening_conditions(request)

	return {
		"opened": opened,
		"sealed": is_sealed(request),
		"closes_at": closes_at(request),
		"conditions": conditions,
		"members": len(members),
		"confirmations": len(members) - len(waiting),
		"confirmed_by": [
			{"member": row.member, "full_name": row.full_name, "confirmed_at": row.confirmed_at}
			for row in request.opening_confirmations
		],
		"received": received_quotes(request.name),
		"expected": cint(request.minimum_expected_quotes),
		"is_member": user in members,
		"can_confirm": request.docstatus == 1
		and not opened
		and user in waiting
		and not unmet(conditions, "bids_closed"),
	}


@frappe.whitelist()
def get_opening_status(name: str) -> ApiResponse[dict]:
	return ApiResponse.success(data=opening_status(sealed_request(name), frappe.session.user))


@frappe.whitelist(methods=["POST"])
def open_quotes(name: str) -> ApiResponse[dict]:
	request = sealed_request(name)
	user = frappe.session.user

	if request.docstatus != 1:
		frappe.throw(_("Submit {0} before opening its quotations.").format(name))

	if cint(request.quotes_opened):
		frappe.throw(_("The quotations for {0} are already open.").format(name))

	if user not in committee_members(request.opening_committee):
		frappe.throw(
			_("Only members of {0} can open these quotations.").format(
				frappe.bold(request.opening_committee)
			),
			frappe.PermissionError,
		)

	if user in {row.member for row in request.opening_confirmations}:
		frappe.throw(_("You have already confirmed the opening of {0}.").format(name))

	blocking = unmet(opening_conditions(request), "bids_closed", "minimum_quotations")
	if blocking:
		frappe.throw(
			"<br>".join(f"{condition['label']}: {condition['detail']}" for condition in blocking),
			title=_("Quotations cannot be opened yet"),
		)

	request.append(
		"opening_confirmations",
		{"member": user, "full_name": get_fullname(user), "confirmed_at": now_datetime()},
	)

	waiting = awaiting_confirmation(request)
	opened = not unmet(opening_conditions(request), "committee_confirmed")
	if opened:
		request.quotes_opened = 1

	request.flags.ignore_permissions = True
	request.save()
	close_opening_tasks(name, None if opened else user)

	message = (
		_("Quotations opened. {0} received.").format(received_quotes(name))
		if opened
		else _("Confirmed. Waiting for {0} more committee member(s).").format(len(waiting))
	)
	return ApiResponse.success(message, opening_status(request, user))
