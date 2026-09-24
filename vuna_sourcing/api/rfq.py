# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate
from frappe.utils.html_utils import sanitize_html

from vuna_sourcing.api.listing import empty_page, my_suppliers
from vuna_sourcing.api.portal import check_party_access
from vuna_sourcing.utils import SUPPLIER

RFQ = "Request for Quotation"
RFQ_ITEM = "Request for Quotation Item"
RFQ_SUPPLIER = "Request for Quotation Supplier"
QUOTE = "Supplier Quotation"
QUOTE_ITEM = "Supplier Quotation Item"

NO_QUOTE = "No Quote"
RECEIVED = "Received"

INVITED = "Invited"
SUBMITTED = "Submitted"
DECLINED = "Declined"
CLOSED = "Closed"


def invited_supplier(rfq: str, supplier: str | None = None) -> str:
	if supplier:
		check_party_access(SUPPLIER, supplier)
		candidates = [supplier]
	else:
		candidates = my_suppliers()

	invited = frappe.get_all(
		RFQ_SUPPLIER,
		filters={"parent": rfq, "parenttype": RFQ, "supplier": ("in", candidates or [""])},
		pluck="supplier",
		limit=1,
	)

	if not invited:
		frappe.throw(_("This quotation request was not sent to you."), frappe.PermissionError)

	return invited[0]


def is_closed(required_by) -> bool:
	return bool(required_by) and getdate(required_by) < getdate(nowdate())


def find_quote(rfq: str, supplier: str) -> dict | None:
	names = frappe.get_all(QUOTE_ITEM, filters={"request_for_quotation": rfq}, pluck="parent")
	if not names:
		return None

	return frappe.db.get_value(
		QUOTE,
		{"name": ("in", set(names)), "supplier": supplier, "docstatus": ("<", 2)},
		["name", "docstatus", "status", "valid_till", "quotation_number", "total", "currency"],
		as_dict=True,
		order_by="creation desc",
	)


def quote_status(rfq: str, supplier: str) -> str | None:
	return frappe.db.get_value(RFQ_SUPPLIER, {"parent": rfq, "supplier": supplier}, "quote_status")


def is_sent(rfq: str, supplier: str) -> bool:
	return quote_status(rfq, supplier) == RECEIVED


def set_quote_status(rfq: str, supplier: str, status: str) -> None:
	row = frappe.db.get_value(RFQ_SUPPLIER, {"parent": rfq, "supplier": supplier}, "name")
	frappe.db.set_value(RFQ_SUPPLIER, row, "quote_status", status, update_modified=False)


def quote_state(row_status: str | None, quote: dict | None, closed: bool) -> str:
	if row_status == NO_QUOTE:
		return DECLINED
	if row_status == RECEIVED or quote:
		return SUBMITTED
	if closed:
		return CLOSED
	return INVITED


@frappe.whitelist()
def get_rfqs(
	supplier: str | None = None,
	status: str | None = None,
	search: str | None = None,
	company: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	if supplier:
		check_party_access(SUPPLIER, supplier)
		suppliers = [supplier]
	else:
		suppliers = my_suppliers()

	if not suppliers:
		return empty_page(start, limit)

	rows = frappe.get_all(
		RFQ_SUPPLIER,
		filters={"parenttype": RFQ, "supplier": ("in", suppliers)},
		fields=["parent", "supplier", "quote_status"],
	)
	if not rows:
		return empty_page(start, limit)

	invited_by_rfq = {row.parent: row for row in rows}
	names = list(invited_by_rfq)

	if search:
		needle = search.strip().lower()
		names = [name for name in names if needle in name.lower()]

	if not names:
		return empty_page(start, limit)

	filters = {"name": ("in", names), "docstatus": 1}
	if company:
		filters["company"] = company

	requests = frappe.get_all(
		RFQ,
		filters=filters,
		fields=["name", "transaction_date", "schedule_date", "company"],
		order_by="transaction_date desc",
	)

	counts = Counter(
		row.parent
		for row in frappe.get_all(
			RFQ_ITEM,
			filters={"parent": ("in", [request.name for request in requests])},
			fields=["parent"],
		)
	)

	listing = []
	for request in requests:
		row = invited_by_rfq[request.name]
		quote = find_quote(request.name, row.supplier)
		listing.append(
			{
				"name": request.name,
				"supplier": row.supplier,
				"transaction_date": request.transaction_date,
				"required_by": request.schedule_date,
				"company": request.company,
				"items": counts.get(request.name, 0),
				"status": quote_state(row.quote_status, quote, is_closed(request.schedule_date)),
				"quote": quote,
			}
		)

	by_status = Counter(row["status"] for row in listing)

	if status:
		wanted = {value.strip() for value in status.split(",") if value.strip()}
		listing = [row for row in listing if row["status"] in wanted]

	start = max(cint(start), 0)
	limit = max(cint(limit), 1)

	return {
		"rows": listing[start : start + limit],
		"total": len(listing),
		"start": start,
		"limit": limit,
		"counts": dict(by_status),
	}


def safe_html(value: str | None) -> str | None:
	if not value:
		return value

	return sanitize_html(value, always_sanitize=True)


def item_description(item) -> dict:
	if item.item_name and item.description:
		return {"item_name": item.item_name, "description": item.description}

	stored = frappe.db.get_value("Item", item.item_code, ["item_name", "description"], as_dict=True) or {}
	return {
		"item_name": item.item_name or stored.get("item_name") or item.item_code,
		"description": item.description or stored.get("description"),
	}


@frappe.whitelist()
def get_rfq(name: str, supplier: str | None = None) -> dict:
	supplier = invited_supplier(name, supplier)
	doc = frappe.get_doc(RFQ, name)

	if doc.docstatus != 1:
		frappe.throw(_("This quotation request is not open."), frappe.PermissionError)

	row = next((row for row in doc.suppliers if row.supplier == supplier), None)
	quote = find_quote(name, supplier)
	closed = is_closed(doc.schedule_date)
	status = quote_state(row.quote_status if row else None, quote, closed)

	quoted_lines = {}
	if quote:
		quoted_lines = {
			line.request_for_quotation_item: line
			for line in frappe.get_all(
				QUOTE_ITEM,
				filters={"parent": quote["name"]},
				fields=["request_for_quotation_item", "rate", "qty", "lead_time_days"],
			)
		}

	items = []
	for item in doc.items:
		quoted = quoted_lines.get(item.name) or {}
		described = item_description(item)
		items.append(
			{
				"name": item.name,
				"item_code": item.item_code,
				"item_name": described.get("item_name"),
				"description": described.get("description"),
				"qty": item.qty,
				"uom": item.uom,
				"required_by": item.schedule_date,
				"supplier_part_no": item.supplier_part_no,
				"rate": quoted.get("rate"),
				"lead_time_days": quoted.get("lead_time_days"),
			}
		)

	return {
		"name": doc.name,
		"supplier": supplier,
		"company": doc.company,
		"transaction_date": doc.transaction_date,
		"required_by": doc.schedule_date,
		"closed": closed,
		"status": status,
		"can_quote": status == INVITED,
		"terms": safe_html(doc.terms),
		"items": items,
		"quote": quote,
		"attachments": frappe.get_all(
			"File",
			filters={"attached_to_doctype": RFQ, "attached_to_name": name},
			fields=["file_name", "file_url"],
		),
	}


ITEM_FIELDS = (
	"item_code",
	"item_name",
	"description",
	"qty",
	"conversion_factor",
	"warehouse",
	"material_request",
	"material_request_item",
	"stock_qty",
	"uom",
)


def build_quote(request, supplier: str):
	doc = frappe.new_doc(QUOTE)
	doc.supplier = supplier
	doc.company = request.company
	doc.transaction_date = nowdate()
	doc.currency = frappe.db.get_value("Supplier", supplier, "default_currency") or frappe.get_cached_value(
		"Company", request.company, "default_currency"
	)
	doc.buying_price_list = frappe.db.get_value(
		"Supplier", supplier, "default_price_list"
	) or frappe.db.get_single_value("Buying Settings", "buying_price_list")

	for item in request.items:
		row = {field: item.get(field) for field in ITEM_FIELDS}
		row.update(
			{
				"request_for_quotation": request.name,
				"request_for_quotation_item": item.name,
				"supplier_part_no": frappe.db.get_value(
					"Item Supplier", {"parent": item.item_code, "supplier": supplier}, "supplier_part_no"
				),
			}
		)
		doc.append("items", row)

	doc.flags.ignore_permissions = True
	return doc


def apply_rates(doc, lines: list[dict]) -> None:
	by_rfq_item = {line.get("rfq_item"): line for line in lines if line.get("rfq_item")}

	for row in doc.items:
		given = by_rfq_item.get(row.request_for_quotation_item)
		if not given:
			continue

		row.rate = flt(given.get("rate"))
		if given.get("lead_time_days") is not None:
			row.lead_time_days = cint(given.get("lead_time_days"))


@frappe.whitelist(methods=["POST"])
def send_quote(
	name: str,
	items: list | str | None = None,
	supplier: str | None = None,
	quotation_number: str | None = None,
	valid_till: str | None = None,
	terms: str | None = None,
) -> dict:
	supplier = invited_supplier(name, supplier)
	request = frappe.get_doc(RFQ, name)

	if request.docstatus != 1:
		frappe.throw(_("This quotation request is not open."), frappe.PermissionError)

	if is_closed(request.schedule_date):
		frappe.throw(_("This quotation request closed on {0}.").format(request.schedule_date))

	if is_sent(name, supplier) or find_quote(name, supplier):
		frappe.throw(_("You have already sent a quotation for this request."))

	lines = frappe.parse_json(items) if isinstance(items, str) else (items or [])

	doc = build_quote(request, supplier)
	apply_rates(doc, lines)
	doc.quotation_number = quotation_number
	doc.valid_till = valid_till
	if terms is not None:
		doc.terms = terms

	unpriced = [row.item_code for row in doc.items if not flt(row.rate)]
	if unpriced:
		frappe.throw(_("Enter a price for every item before you send it: {0}").format(", ".join(unpriced)))
	if not doc.valid_till:
		frappe.throw(_("Tell us how long your prices stay valid."))

	doc.flags.ignore_permissions = True
	doc.save()
	set_quote_status(name, supplier, RECEIVED)

	return get_rfq(name, supplier)


@frappe.whitelist(methods=["POST"])
def decline_quote(name: str, reason: str, supplier: str | None = None) -> dict:
	supplier = invited_supplier(name, supplier)

	if not (reason or "").strip():
		frappe.throw(_("Please tell us why you are not quoting."))

	if is_sent(name, supplier):
		frappe.throw(_("You have already sent a quotation for this request."))

	set_quote_status(name, supplier, NO_QUOTE)

	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": RFQ,
			"reference_name": name,
			"content": _("{0} declined to quote: {1}").format(supplier, reason),
		}
	).insert(ignore_permissions=True)

	return get_rfq(name, supplier)
