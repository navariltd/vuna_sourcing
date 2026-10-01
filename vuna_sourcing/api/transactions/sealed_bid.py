# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.form.assign_to import add as assign
from frappe.query_builder.functions import IfNull
from frappe.utils import cint, format_datetime, get_fullname, getdate, now_datetime

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.bidding import SEALED_BID, closes_at, is_closed, is_sealed
from vuna_sourcing.api.transactions.supplier import (
	QUOTE_PENDING,
	RFQ,
	SUBMISSION_STATUS_FIELD,
	SUPPLIER_QUOTATION,
	SUPPLIER_QUOTATION_ITEM,
)

COMMITTEE = "RFQ Opening Committee"
COMMITTEE_MEMBER = "RFQ Opening Committee Member"


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


def opening_status(request, user: str) -> dict:
	members = committee_members(request.opening_committee)
	waiting = awaiting_confirmation(request)
	opened = bool(cint(request.quotes_opened))
	closed = is_closed(request)

	return {
		"opened": opened,
		"sealed": is_sealed(request),
		"closed": closed,
		"closes_at": closes_at(request),
		"members": len(members),
		"confirmations": len(members) - len(waiting),
		"waiting": [get_fullname(member) for member in waiting],
		"confirmed_by": [
			{"member": row.member, "full_name": row.full_name, "confirmed_at": row.confirmed_at}
			for row in request.opening_confirmations
		],
		"received": received_quotes(request.name),
		"expected": cint(request.minimum_expected_quotes),
		"is_member": user in members,
		"can_confirm": request.docstatus == 1 and not opened and closed and user in waiting,
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

	if not is_closed(request):
		frappe.throw(
			_("Quotations can only be opened after bids close at {0}.").format(
				format_datetime(closes_at(request))
			)
		)

	if user not in committee_members(request.opening_committee):
		frappe.throw(
			_("Only members of {0} can open these quotations.").format(
				frappe.bold(request.opening_committee)
			),
			frappe.PermissionError,
		)

	if user in {row.member for row in request.opening_confirmations}:
		frappe.throw(_("You have already confirmed the opening of {0}.").format(name))

	received = received_quotes(name)
	expected = cint(request.minimum_expected_quotes)
	if received < expected:
		frappe.throw(
			_("{0} quotation(s) received for {1}, fewer than the {2} expected.").format(
				received, name, expected
			),
			title=_("Not Enough Quotations"),
		)

	request.append(
		"opening_confirmations",
		{"member": user, "full_name": get_fullname(user), "confirmed_at": now_datetime()},
	)

	waiting = awaiting_confirmation(request)
	opened = not waiting
	if opened:
		request.quotes_opened = 1

	request.flags.ignore_permissions = True
	request.save()
	close_opening_tasks(name, None if opened else user)

	message = (
		_("Quotations opened. {0} received.").format(received)
		if opened
		else _("Confirmed. Waiting for {0} more committee member(s).").format(len(waiting))
	)
	return ApiResponse.success(message, opening_status(request, user))
