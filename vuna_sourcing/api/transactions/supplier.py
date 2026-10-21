# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _
from frappe.utils import cint, flt, format_datetime, nowdate

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.bidding import (
	AWARD,
	AWARD_ITEM,
	closes_at,
	closes_at_iso,
	closing_passed,
	is_closed,
	is_open_bid,
	is_sealed,
)
from vuna_sourcing.api.transactions.common import (
	balance,
	company_currency,
	distinct,
	empty_page,
	find_documents,
	item_description,
	line_item,
	month_starts,
	monthly_totals,
	my_parties,
	outstanding_statement,
	owned_document,
	page_of,
	party_scope,
	payments_against,
	returns_against,
	safe_html,
	status_counts,
)
from vuna_sourcing.utils import SUPPLIER
from vuna_sourcing.vuna_sourcing.doctype.rfq_bid_log.rfq_bid_log import record_bid

RFQ = "Request for Quotation"
RFQ_ITEM = "Request for Quotation Item"
RFQ_SUPPLIER = "Request for Quotation Supplier"
SUPPLIER_QUOTATION = "Supplier Quotation"
SUPPLIER_QUOTATION_ITEM = "Supplier Quotation Item"
PURCHASE_ORDER = "Purchase Order"
PURCHASE_INVOICE = "Purchase Invoice"

NO_QUOTE = "No Quote"
RECEIVED = "Received"

INVITED = "Invited"
DRAFT = "Draft"
SUBMITTED = "Submitted"
BIDDING = "Bidding"
DECLINED = "Declined"
CLOSED = "Closed"
AWARDED_TO_YOU = "Awarded"
NOT_SELECTED = "Not Selected"

SUBMISSION_STATUS_FIELD = "supplier_submission_status"
QUOTE_PENDING = "Pending"
QUOTE_SENT = "Submitted"

QUOTATION_FIELDS = [
	"name",
	"supplier",
	"transaction_date",
	"valid_till",
	"quotation_number",
	"total",
	"currency",
	"status",
	"docstatus",
]

ORDER_FIELDS = [
	"name",
	"supplier",
	"transaction_date",
	"schedule_date",
	"currency",
	"grand_total",
	"status",
	"per_received",
	"per_billed",
]

INVOICE_FIELDS = [
	"name",
	"supplier",
	"posting_date",
	"due_date",
	"bill_no",
	"currency",
	"grand_total",
	"outstanding_amount",
	"is_return",
	"return_against",
	"status",
]

QUOTE_ITEM_FIELDS = (
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


def my_suppliers(user: str | None = None) -> list[str]:
	return my_parties(SUPPLIER, user)


def supplier_scope(supplier: str | None = None) -> list[str]:
	return party_scope(SUPPLIER, supplier)


def supplier_filters(suppliers: list[str]) -> dict:
	return {"supplier": ("in", suppliers or [""]), "docstatus": ("<", 2)}


def supplier_document(doctype: str, name: str, supplier: str | None = None):
	return owned_document(doctype, name, supplier_filters(supplier_scope(supplier)))


def supplier_documents(
	doctype: str,
	suppliers: list[str],
	search: str | None,
	fields: list[str],
	order_by: str = "creation desc",
	**filters,
) -> list:
	return find_documents(
		doctype, {**supplier_filters(suppliers), **filters}, search, fields, order_by=order_by
	)


def invited_supplier(rfq: str, supplier: str | None = None) -> str:
	"""Validate the Supplier was sent the quotation"""
	invited = frappe.get_all(
		RFQ_SUPPLIER,
		filters={"parent": rfq, "parenttype": RFQ, "supplier": ("in", supplier_scope(supplier) or [""])},
		pluck="supplier",
		limit=1,
	)

	if not invited:
		frappe.throw(_("This quotation request was not sent to you."), frappe.PermissionError)

	return invited[0]


def find_quote(rfq: str, supplier: str) -> dict | None:
	names = frappe.get_all(SUPPLIER_QUOTATION_ITEM, filters={"request_for_quotation": rfq}, pluck="parent")
	if not names:
		return None

	return frappe.db.get_value(
		SUPPLIER_QUOTATION,
		{"name": ("in", set(names)), "supplier": supplier, "docstatus": ("<", 2)},
		[
			"name",
			"docstatus",
			"status",
			"valid_till",
			"quotation_number",
			"total",
			"currency",
			SUBMISSION_STATUS_FIELD,
		],
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


def is_pending(quote) -> bool:
	return bool(quote) and quote.get(SUBMISSION_STATUS_FIELD) == QUOTE_PENDING


def quote_state(
	row_status: str | None,
	quote: dict | None,
	closed: bool,
	open_bid: bool = False,
	outcome: str | None = None,
) -> str:
	if outcome in (AWARDED_TO_YOU, NOT_SELECTED):
		return outcome
	if row_status == NO_QUOTE:
		return DECLINED
	if row_status == RECEIVED or (quote and not is_pending(quote)):
		return BIDDING if open_bid and not closed else SUBMITTED
	if closed:
		return CLOSED
	if quote:
		return DRAFT
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
	suppliers = supplier_scope(supplier)
	if not suppliers:
		return empty_page(start, limit)

	rows = frappe.get_all(
		RFQ_SUPPLIER,
		filters={"parenttype": RFQ, "supplier": ("in", suppliers)},
		fields=["parent", "supplier", "quote_status", "award_outcome"],
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
		fields=[
			"name",
			"transaction_date",
			"schedule_date",
			"company",
			"bidding_method",
			"bid_closing",
			"quotes_opened",
		],
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
				"closes_at": closes_at_iso(request),
				"bidding_method": request.bidding_method,
				"company": request.company,
				"items": counts.get(request.name, 0),
				"status": quote_state(
					row.quote_status,
					quote,
					is_closed(request),
					is_open_bid(request),
					row.award_outcome,
				),
				"quote": quote,
			}
		)

	by_status = dict(Counter(row["status"] for row in listing))

	if status:
		wanted = {value.strip() for value in status.split(",") if value.strip()}
		listing = [row for row in listing if row["status"] in wanted]

	return page_of(listing, start, limit, counts=by_status)


@frappe.whitelist()
def get_rfq(name: str, supplier: str | None = None) -> dict:
	supplier = invited_supplier(name, supplier)
	doc = frappe.get_doc(RFQ, name)

	if doc.docstatus != 1:
		frappe.throw(_("This quotation request is not open."), frappe.PermissionError)

	row = next((row for row in doc.suppliers if row.supplier == supplier), None)
	quote = find_quote(name, supplier)
	closed = is_closed(doc)
	open_bid = is_open_bid(doc)
	status = quote_state(
		row.quote_status if row else None,
		quote,
		closed,
		open_bid,
		row.award_outcome if row else None,
	)

	quoted_lines = {}
	if quote:
		quoted_lines = {
			line.request_for_quotation_item: line
			for line in frappe.get_all(
				SUPPLIER_QUOTATION_ITEM,
				filters={"parent": quote["name"]},
				fields=["request_for_quotation_item", "rate", "qty", "lead_time_days"],
			)
		}

	won = items_awarded_to(name, supplier)
	items = []
	for item in doc.items:
		quoted = quoted_lines.get(item.name) or {}
		items.append(
			{
				"name": item.name,
				"item_code": item.item_code,
				**item_description(item),
				"qty": item.qty,
				"uom": item.uom,
				"required_by": item.schedule_date,
				"supplier_part_no": item.supplier_part_no,
				"rate": quoted.get("rate") or None,
				"lead_time_days": quoted.get("lead_time_days"),
				"awarded_to_you": item.name in won,
			}
		)

	return {
		"name": doc.name,
		"supplier": supplier,
		"company": doc.company,
		"transaction_date": doc.transaction_date,
		"required_by": doc.schedule_date,
		"closes_at": closes_at_iso(doc),
		"bidding_method": doc.bidding_method,
		"sealed": is_sealed(doc),
		"open_bid": open_bid,
		"closed": closed,
		"status": status,
		"can_quote": status in (INVITED, DRAFT, BIDDING),
		"terms": safe_html(doc.terms),
		"items": items,
		"quote": quote,
		"attachments": frappe.get_all(
			"File",
			filters={"attached_to_doctype": RFQ, "attached_to_name": name},
			fields=["file_name", "file_url"],
		),
	}


def items_awarded_to(request: str, supplier: str) -> set[str]:
	award = frappe.qb.DocType(AWARD)
	item = frappe.qb.DocType(AWARD_ITEM)
	return {
		row[0]
		for row in (
			frappe.qb.from_(item)
			.join(award)
			.on(award.name == item.parent)
			.select(item.request_for_quotation_item)
			.where(award.request_for_quotation == request)
			.where(award.docstatus == 1)
			.where(item.supplier == supplier)
		).run()
	}


def build_quote(request, supplier: str):
	doc = frappe.new_doc(SUPPLIER_QUOTATION)
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
		row = {field: item.get(field) for field in QUOTE_ITEM_FIELDS}
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
	typed = {}

	for row in doc.items:
		given = by_rfq_item.get(row.request_for_quotation_item)
		if not given:
			typed[row.request_for_quotation_item] = flt(row.rate)
			continue

		row.rate = flt(given.get("rate"))
		typed[row.request_for_quotation_item] = row.rate
		if given.get("lead_time_days") is not None:
			row.lead_time_days = cint(given.get("lead_time_days"))

	doc.flags.supplier_rates = typed


def open_request(name: str):
	request = frappe.get_doc(RFQ, name)

	if request.docstatus != 1:
		frappe.throw(_("This quotation request is not open."), frappe.PermissionError)

	if is_closed(request):
		if closing_passed(request):
			frappe.throw(
				_("Bids for this request closed at {0}.").format(format_datetime(closes_at(request)))
			)
		frappe.throw(_("Bids for this request have closed."))

	return request


def draft_or_new_quote(request, supplier: str):
	quote = find_quote(request.name, supplier)

	if is_pending(quote) or (quote and is_open_bid(request)):
		doc = frappe.get_doc(SUPPLIER_QUOTATION, quote.name)
		doc.flags.ignore_permissions = True
		doc.flags.placing_bid = True
		return doc

	if quote or is_sent(request.name, supplier):
		frappe.throw(_("You have already sent a quotation for this request."))

	return build_quote(request, supplier)


def fill_quote(
	doc,
	items: list | str | None,
	quotation_number: str | None,
	valid_till: str | None,
	terms: str | None,
) -> None:
	lines = frappe.parse_json(items) if isinstance(items, str) else (items or [])
	apply_rates(doc, lines)
	doc.quotation_number = quotation_number
	doc.valid_till = valid_till
	if terms is not None:
		doc.terms = terms


@frappe.whitelist(methods=["POST"])
def save_quote(
	name: str,
	items: list | str | None = None,
	supplier: str | None = None,
	quotation_number: str | None = None,
	valid_till: str | None = None,
	terms: str | None = None,
) -> ApiResponse[dict]:
	supplier = invited_supplier(name, supplier)
	request = open_request(name)
	if is_open_bid(request) and is_sent(name, supplier):
		frappe.throw(_("You have already bid on this request. Place a new bid in the bid room instead."))

	doc = draft_or_new_quote(request, supplier)

	fill_quote(doc, items, quotation_number, valid_till, terms)
	doc.set(SUBMISSION_STATUS_FIELD, QUOTE_PENDING)
	doc.save()

	return ApiResponse.success(_("Draft saved."), get_rfq(name, supplier))


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
	request = open_request(name)
	doc = draft_or_new_quote(request, supplier)

	fill_quote(doc, items, quotation_number, valid_till, terms)

	unpriced = [row.item_code for row in doc.items if not flt(row.rate)]
	if unpriced:
		frappe.throw(_("Enter a price for every item before you send it: {0}").format(", ".join(unpriced)))
	if not doc.valid_till:
		frappe.throw(_("Tell us how long your prices stay valid."))

	doc.set(SUBMISSION_STATUS_FIELD, QUOTE_SENT)
	doc.save()
	set_quote_status(name, supplier, RECEIVED)
	if is_open_bid(request):
		record_bid(doc, name)

	return get_rfq(name, supplier)


@frappe.whitelist(methods=["POST"])
def decline_quote(name: str, reason: str, supplier: str | None = None) -> dict:
	supplier = invited_supplier(name, supplier)

	if not (reason or "").strip():
		frappe.throw(_("Please tell us why you are not quoting."))

	if is_sent(name, supplier):
		frappe.throw(_("You have already sent a quotation for this request."))

	draft = find_quote(name, supplier)
	if is_pending(draft):
		frappe.delete_doc(SUPPLIER_QUOTATION, draft.name, ignore_permissions=True)

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


def quotation_status(row) -> str:
	return row.get("status") or ("Submitted" if row.get("docstatus") == 1 else "Draft")


@frappe.whitelist()
def get_supplier_quotations(
	supplier: str | None = None,
	search: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	suppliers = supplier_scope(supplier)
	if not suppliers:
		return empty_page(start, limit)

	quotations = supplier_documents(
		SUPPLIER_QUOTATION,
		suppliers,
		search,
		QUOTATION_FIELDS,
		order_by="transaction_date desc, creation desc",
	)
	if not quotations:
		return empty_page(start, limit)

	answered = {}
	counts = Counter()
	for row in frappe.get_all(
		SUPPLIER_QUOTATION_ITEM,
		filters={"parent": ("in", [quotation.name for quotation in quotations])},
		fields=["parent", "request_for_quotation"],
	):
		counts[row.parent] += 1
		if row.request_for_quotation:
			answered.setdefault(row.parent, row.request_for_quotation)

	return page_of(
		[
			{
				"name": quotation.name,
				"supplier": quotation.supplier,
				"transaction_date": quotation.transaction_date,
				"valid_till": quotation.valid_till,
				"quotation_number": quotation.quotation_number,
				"total": quotation.total,
				"currency": quotation.currency,
				"items": counts.get(quotation.name, 0),
				"rfq": answered.get(quotation.name),
				"status": quotation_status(quotation),
			}
			for quotation in quotations
		],
		start,
		limit,
	)


@frappe.whitelist()
def get_supplier_quotation(name: str, supplier: str | None = None) -> dict:
	doc = supplier_document(SUPPLIER_QUOTATION, name, supplier)

	items = [
		line_item(item, lead_time_days=item.lead_time_days, rfq=item.request_for_quotation)
		for item in doc.items
	]

	return {
		"name": doc.name,
		"supplier": doc.supplier,
		"status": quotation_status(doc),
		"transaction_date": doc.transaction_date,
		"valid_till": doc.valid_till,
		"quotation_number": doc.quotation_number,
		"currency": doc.currency,
		"total": doc.total,
		"grand_total": doc.grand_total,
		"terms": safe_html(doc.terms),
		"rfq": next((item["rfq"] for item in items if item["rfq"]), None),
		"items": items,
	}


@frappe.whitelist()
def get_purchase_orders(
	supplier: str | None = None,
	search: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	suppliers = supplier_scope(supplier)
	if not suppliers:
		return empty_page(start, limit)

	orders = supplier_documents(PURCHASE_ORDER, suppliers, search, ORDER_FIELDS)

	return page_of(
		[
			{
				"name": order.name,
				"supplier": order.supplier,
				"transaction_date": order.transaction_date,
				"required_by": order.schedule_date,
				"currency": order.currency,
				"grand_total": order.grand_total,
				"received": flt(order.per_received, 1),
				"billed": flt(order.per_billed, 1),
				"status": order.status or "To Receive and Bill",
			}
			for order in orders
		],
		start,
		limit,
	)


@frappe.whitelist()
def get_purchase_order(name: str, supplier: str | None = None) -> dict:
	doc = supplier_document(PURCHASE_ORDER, name, supplier)

	items = [
		line_item(
			item,
			received_qty=flt(item.received_qty),
			outstanding_qty=max(flt(item.qty) - flt(item.received_qty), 0),
			required_by=item.schedule_date,
		)
		for item in doc.items
	]

	return {
		"name": doc.name,
		"supplier": doc.supplier,
		"status": doc.status,
		"transaction_date": doc.transaction_date,
		"required_by": doc.schedule_date,
		"currency": doc.currency,
		"total": doc.total,
		"grand_total": doc.grand_total,
		"received": flt(doc.per_received, 1),
		"billed": flt(doc.per_billed, 1),
		"terms": safe_html(doc.terms),
		"items": items,
		"receipts": receipts_against(doc.name),
	}


def receipts_against(order: str) -> list[dict]:
	names = frappe.get_all(
		"Purchase Receipt Item",
		filters={"purchase_order": order, "docstatus": 1},
		pluck="parent",
	)
	if not names:
		return []

	return frappe.get_all(
		"Purchase Receipt",
		filters={"name": ("in", set(names)), "docstatus": 1},
		fields=["name", "posting_date", "status"],
		order_by="posting_date desc",
	)


@frappe.whitelist()
def get_purchase_invoices(
	supplier: str | None = None,
	search: str | None = None,
	debit_notes: bool = False,
	start: int = 0,
	limit: int = 20,
) -> dict:
	suppliers = supplier_scope(supplier)
	if not suppliers:
		return empty_page(start, limit)

	invoices = supplier_documents(
		PURCHASE_INVOICE, suppliers, search, INVOICE_FIELDS, is_return=cint(debit_notes)
	)

	return page_of(
		[
			{
				"name": invoice.name,
				"supplier": invoice.supplier,
				"posting_date": invoice.posting_date,
				"due_date": invoice.due_date,
				"bill_no": invoice.bill_no,
				"currency": invoice.currency,
				"grand_total": invoice.grand_total,
				"outstanding_amount": invoice.outstanding_amount,
				"return_against": invoice.return_against,
				"is_return": bool(invoice.is_return),
				"status": invoice.status or "Unpaid",
			}
			for invoice in invoices
		],
		start,
		limit,
	)


@frappe.whitelist()
def get_purchase_invoice(name: str, supplier: str | None = None) -> dict:
	doc = supplier_document(PURCHASE_INVOICE, name, supplier)

	items = [line_item(item, purchase_order=item.purchase_order) for item in doc.items]

	return {
		"name": doc.name,
		"supplier": doc.supplier,
		"status": doc.status,
		"is_return": bool(doc.is_return),
		"return_against": doc.return_against,
		"bill_no": doc.bill_no,
		"bill_date": doc.bill_date,
		"posting_date": doc.posting_date,
		"due_date": doc.due_date,
		"currency": doc.currency,
		"total": doc.total,
		"grand_total": doc.grand_total,
		"outstanding_amount": doc.outstanding_amount,
		"on_hold": bool(doc.on_hold),
		"hold_reason": doc.hold_comment if doc.on_hold else None,
		"release_date": doc.release_date if doc.on_hold else None,
		"terms": safe_html(doc.terms),
		"purchase_orders": distinct(items, "purchase_order"),
		"items": items,
		"payments": payments_against(PURCHASE_INVOICE, doc.name),
		"debit_notes": returns_against(PURCHASE_INVOICE, doc.name),
	}


@frappe.whitelist()
def get_account_statement(supplier: str | None = None) -> dict:
	parties = supplier_scope(supplier)
	if not parties:
		return {"report_date": None, "companies": []}

	return outstanding_statement("Payable", SUPPLIER, parties)


OPEN_ORDER_STATUSES = ("To Receive and Bill", "To Receive", "To Bill")


@frappe.whitelist()
def get_dashboard(supplier: str | None = None) -> dict:
	suppliers = supplier_scope(supplier)
	if not suppliers:
		return {}

	submitted = {"supplier": ("in", suppliers), "docstatus": 1}
	invited = get_rfqs(supplier=supplier, status=f"{INVITED},{DRAFT},{BIDDING}", limit=100)
	open_orders = frappe.get_all(
		PURCHASE_ORDER,
		filters={**submitted, "status": ("in", OPEN_ORDER_STATUSES)},
		fields=[
			"name",
			"transaction_date",
			"schedule_date",
			"grand_total",
			"currency",
			"status",
			"per_received",
		],
		order_by="transaction_date desc",
	)
	paid = frappe.get_all(
		"Payment Entry",
		filters={
			"payment_type": "Pay",
			"party_type": SUPPLIER,
			"party": ("in", suppliers),
			"docstatus": 1,
			"posting_date": (">=", month_starts()[0]),
		},
		pluck="base_paid_amount",
	)

	return {
		"currency": company_currency(),
		"awaiting_quote": invited["total"],
		"open_orders": len(open_orders),
		"balance": balance(outstanding_statement("Payable", SUPPLIER, suppliers)),
		"paid_last_year": flt(sum(flt(amount) for amount in paid), 2),
		"orders_by_month": monthly_totals(PURCHASE_ORDER, submitted, "transaction_date", "base_grand_total"),
		"invoices_by_status": status_counts(PURCHASE_INVOICE, {**submitted, "is_return": 0}),
		"rfqs_closing": sorted(invited["rows"], key=lambda row: str(row["closes_at"] or "9999"))[:5],
		"open_order_rows": [{**order, "received": flt(order.per_received, 1)} for order in open_orders[:5]],
	}
