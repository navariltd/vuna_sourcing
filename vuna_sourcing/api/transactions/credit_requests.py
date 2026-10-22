# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, strip_html

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.common import empty_page, find_documents, page_of, party_scope
from vuna_sourcing.utils import CUSTOMER
from vuna_sourcing.vuna_sourcing.doctype.credit_note_request.credit_note_request import (
	DOCTYPE,
	EDITABLE_AFTER_SUBMIT,
	OPEN_STATUSES,
	RETURNED,
	SALES_INVOICE,
	creditable_invoice,
	credited_quantities,
	invoice_lines,
	open_request_for,
)

MAX_LINES = 200
DETAILS_LENGTH = 1000

REQUEST_FIELDS = [
	"name",
	"sales_invoice",
	"transaction_date",
	"reason",
	"currency",
	"total_amount",
	"request_status",
	"credit_note",
]


def credit_requests_enabled() -> bool:
	return bool(cint(frappe.db.get_single_value("Sourcing Settings", "allow_customer_credit_requests")))


def ensure_enabled() -> None:
	if not credit_requests_enabled():
		frappe.throw(_("Credit note requests on the portal are turned off."), frappe.PermissionError)


def requesting_customer(customer: str | None) -> str:
	if not customer:
		frappe.throw(_("Choose the customer account this request is for."))

	party_scope(CUSTOMER, customer)
	return customer


def own_invoice(name: str | None, customer: str) -> str:
	if not name or not frappe.db.exists(SALES_INVOICE, {"name": name, "customer": customer, "docstatus": 1}):
		frappe.throw(_("This invoice does not belong to you."), frappe.PermissionError)

	return name


def own_request(name: str, customers: list[str]):
	mine = frappe.db.get_value(
		DOCTYPE, {"name": name, "customer": ("in", customers or [""]), "docstatus": ("!=", 0)}, "name"
	)
	if not mine:
		frappe.throw(_("This request does not belong to you."), frappe.PermissionError)

	return frappe.get_doc(DOCTYPE, mine)


def reason_options() -> list[str]:
	return [option for option in (frappe.get_meta(DOCTYPE).get_options("reason") or "").split("\n") if option]


def requested_lines(items) -> list[dict]:
	lines = frappe.parse_json(items) if isinstance(items, str) else items
	if not isinstance(lines, list):
		frappe.throw(_("Choose at least one item to credit."))

	merged = {}
	for line in lines:
		if not isinstance(line, dict):
			frappe.throw(_("Your request could not be read. Refresh the page and try again."))

		row = cstr(line.get("sales_invoice_item")).strip()
		qty = flt(line.get("qty"))
		if not row:
			continue
		if not math.isfinite(qty) or qty < 0:
			frappe.throw(_("Enter a quantity of zero or more on every line."))

		merged[row] = merged.get(row, 0) + qty

	if len(merged) > MAX_LINES:
		frappe.throw(_("A request can have at most {0} lines.").format(MAX_LINES))

	return [{"sales_invoice_item": row, "qty": qty} for row, qty in merged.items() if qty > 0]


def fill_request(doc, items, reason: str | None, description: str | None) -> None:
	doc.reason = cstr(reason).strip()
	doc.description = cstr(description).strip()[:DETAILS_LENGTH] or None
	doc.set("items", [])
	for line in requested_lines(items):
		doc.append("items", line)

	doc.flags.ignore_permissions = True


def invoice_header(invoice) -> dict:
	return {
		"name": invoice.name,
		"posting_date": invoice.posting_date,
		"po_no": invoice.po_no,
		"currency": invoice.currency,
		"total": invoice.total,
		"total_taxes": invoice.total_taxes_and_charges,
		"grand_total": invoice.grand_total,
	}


def form_line(line: dict, requested: float) -> dict:
	return {
		**line,
		"description": strip_html(line.get("description") or "").strip() or None,
		"qty": requested,
	}


def request_view(doc) -> dict:
	credit_note = None
	if doc.credit_note:
		credit_note = frappe.db.get_value(
			SALES_INVOICE,
			doc.credit_note,
			["name", "posting_date", "grand_total", "status"],
			as_dict=True,
		)

	return {
		"name": doc.name,
		"customer": doc.customer,
		"sales_invoice": doc.sales_invoice,
		"status": doc.request_status,
		"transaction_date": doc.transaction_date,
		"reason": doc.reason,
		"description": doc.description,
		"currency": doc.currency,
		"total_qty": doc.total_qty,
		"total_amount": doc.total_amount,
		"review_remarks": doc.review_remarks,
		"reviewed_on": doc.reviewed_on,
		"editable": doc.request_status == RETURNED and credit_requests_enabled(),
		"withdrawable": doc.docstatus == 1 and doc.request_status in EDITABLE_AFTER_SUBMIT,
		"credit_note": credit_note,
		"items": [
			{
				"sales_invoice_item": row.sales_invoice_item,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"uom": row.uom,
				"rate": row.rate,
				"qty": row.qty,
				"amount": row.amount,
			}
			for row in doc.items
		],
	}


def invoice_credit_state(invoice) -> dict:
	enabled = credit_requests_enabled()
	open_request = open_request_for(invoice.name)
	creditable = (
		enabled
		and not invoice.is_return
		and not open_request
		and any(line["available_qty"] > 0 for line in invoice_lines(invoice))
	)

	return {
		"can_request": bool(creditable),
		"open_request": open_request,
	}


@frappe.whitelist()
def get_credit_requests(
	customer: str | None = None,
	search: str | None = None,
	status: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> ApiResponse[dict]:
	customers = party_scope(CUSTOMER, customer)
	if not customers:
		return ApiResponse.success(data={**empty_page(start, limit), "can_request": False})

	filters = {"customer": ("in", customers), "docstatus": ("!=", 0)}
	requests = find_documents(
		DOCTYPE, filters, search, REQUEST_FIELDS, search_fields=("name", "sales_invoice")
	)
	counts = {}
	for row in requests:
		counts[row.request_status] = counts.get(row.request_status, 0) + 1

	rows = [
		{
			"name": row.name,
			"sales_invoice": row.sales_invoice,
			"transaction_date": row.transaction_date,
			"reason": row.reason,
			"currency": row.currency,
			"total_amount": row.total_amount,
			"status": row.request_status,
			"credit_note": row.credit_note,
		}
		for row in requests
		if not status or row.request_status == status
	]

	return ApiResponse.success(
		data={**page_of(rows, start, limit, counts), "can_request": credit_requests_enabled()}
	)


@frappe.whitelist()
def get_credit_request(name: str, customer: str | None = None) -> ApiResponse[dict]:
	return ApiResponse.success(data=request_view(own_request(name, party_scope(CUSTOMER, customer))))


@frappe.whitelist()
def get_creditable_invoices(customer: str, search: str | None = None) -> ApiResponse[list]:
	ensure_enabled()
	customer = requesting_customer(customer)

	invoices = find_documents(
		SALES_INVOICE,
		{"customer": customer, "docstatus": 1, "is_return": 0},
		search,
		["name", "posting_date", "po_no", "currency", "grand_total"],
		search_fields=("name", "po_no"),
		order_by="posting_date desc, creation desc",
	)
	names = [invoice.name for invoice in invoices]
	if not names:
		return ApiResponse.success(data=[])

	invoiced = {}
	for row in frappe.get_all(
		"Sales Invoice Item",
		filters={"parenttype": SALES_INVOICE, "parent": ("in", names)},
		fields=["name", "parent", "qty"],
	):
		invoiced.setdefault(row.parent, []).append(row)

	credited = credited_quantities(names, customer)
	open_requests = dict(
		frappe.get_all(
			DOCTYPE,
			filters={
				"sales_invoice": ("in", names),
				"docstatus": 1,
				"request_status": ("in", OPEN_STATUSES),
			},
			fields=["sales_invoice", "name"],
			as_list=True,
		)
	)

	rows = []
	for invoice in invoices:
		open_qty = sum(
			max(flt(row.qty) - credited.get(row.name, 0), 0) for row in invoiced.get(invoice.name, [])
		)
		if open_qty <= 0:
			continue

		rows.append(
			{
				"name": invoice.name,
				"posting_date": invoice.posting_date,
				"po_no": invoice.po_no,
				"currency": invoice.currency,
				"grand_total": invoice.grand_total,
				"open_request": open_requests.get(invoice.name),
			}
		)
		if len(rows) >= 20:
			break

	return ApiResponse.success(data=rows)


@frappe.whitelist()
def get_credit_form(
	customer: str, sales_invoice: str | None = None, name: str | None = None
) -> ApiResponse[dict]:
	customer = requesting_customer(customer)
	if not credit_requests_enabled():
		return ApiResponse.error(_("Credit note requests on the portal are turned off."))

	request = None
	if name:
		request = own_request(name, [customer])
		if request.request_status != RETURNED:
			return ApiResponse.error(_("This request is with our team, so it can no longer be changed."))
		sales_invoice = request.sales_invoice
	elif not sales_invoice:
		return ApiResponse.error(_("Choose the invoice you want credited."))

	invoice = creditable_invoice(own_invoice(sales_invoice, customer), customer)

	if not request:
		open_request = open_request_for(invoice.name)
		if open_request:
			return ApiResponse.error(
				_("Request {0} for this invoice is still {1}. Follow it up there.").format(
					open_request.name, _(open_request.request_status).lower()
				),
				data={"open_request": open_request.name},
			)

	lines = invoice_lines(invoice)
	if not any(line["available_qty"] > 0 for line in lines):
		return ApiResponse.error(_("Invoice {0} has already been fully credited.").format(invoice.name))

	requested = {row.sales_invoice_item: flt(row.qty) for row in request.items} if request else {}

	return ApiResponse.success(
		data={
			"invoice": invoice_header(invoice),
			"reasons": reason_options(),
			"lines": [form_line(line, requested.get(line["sales_invoice_item"], 0)) for line in lines],
			"request": {
				"name": request.name,
				"reason": request.reason,
				"description": request.description,
				"review_remarks": request.review_remarks,
			}
			if request
			else None,
		}
	)


@frappe.whitelist(methods=["POST"])
def submit_credit_request(
	customer: str,
	sales_invoice: str,
	items: list | str | None = None,
	reason: str | None = None,
	description: str | None = None,
) -> ApiResponse[dict]:
	ensure_enabled()
	customer = requesting_customer(customer)
	own_invoice(sales_invoice, customer)

	doc = frappe.new_doc(DOCTYPE)
	doc.update({"customer": customer, "sales_invoice": sales_invoice, "requested_by": frappe.session.user})
	fill_request(doc, items, reason, description)
	doc.insert()
	doc.submit()

	return ApiResponse.success(_("Request sent. Our accounts team will review it."), request_view(doc))


@frappe.whitelist(methods=["POST"])
def resubmit_credit_request(
	customer: str,
	name: str,
	items: list | str | None = None,
	reason: str | None = None,
	description: str | None = None,
) -> ApiResponse[dict]:
	ensure_enabled()
	doc = own_request(name, [requesting_customer(customer)])
	if doc.request_status != RETURNED:
		frappe.throw(_("Only a request we sent back for changes can be resubmitted."))

	fill_request(doc, items, reason, description)
	doc.resubmit()

	return ApiResponse.success(
		_("Request resubmitted. Our accounts team will review it again."), request_view(doc)
	)


@frappe.whitelist(methods=["POST"])
def withdraw_credit_request(customer: str, name: str) -> ApiResponse[dict]:
	doc = own_request(name, [requesting_customer(customer)])
	if doc.docstatus != 1 or doc.request_status not in EDITABLE_AFTER_SUBMIT:
		frappe.throw(_("This request has been decided, so it can no longer be withdrawn."))

	doc.flags.ignore_permissions = True
	doc.flags.withdrawn_by_customer = True
	doc.cancel()
	doc.add_comment("Info", _("Withdrawn by the customer on the portal."))

	return ApiResponse.success(_("Request withdrawn."), request_view(doc))
