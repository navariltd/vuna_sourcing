# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from collections import Counter
from collections.abc import Callable

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.branches import (
	BRANCH_FIELD,
	branch_restrictions,
	customer_scope_filters,
	requested_branches,
)
from vuna_sourcing.api.transactions.common import (
	all_of,
	balance,
	company_currency,
	distinct,
	empty_page,
	find_documents,
	line_item,
	monthly_totals,
	outstanding_statement,
	owned_document,
	page_of,
	party_scope,
	payments_against,
	returns_against,
	safe_html,
	statement_page,
	status_counts,
	submitted_parents,
)
from vuna_sourcing.api.transactions.credit_requests import invoice_credit_state
from vuna_sourcing.api.transactions.customer_orders import (
	FROM_PORTAL_FIELD,
	ORDER_PENDING,
	ORDER_SUBMITTED,
	PORTAL_STATUS_FIELD,
	can_order,
)
from vuna_sourcing.utils import CUSTOMER

QUOTATION = "Quotation"
SALES_ORDER = "Sales Order"
DELIVERY_NOTE = "Delivery Note"
SALES_INVOICE = "Sales Invoice"

QUOTATION_FIELDS = [
	"name",
	"party_name",
	"transaction_date",
	"valid_till",
	BRANCH_FIELD,
	"currency",
	"grand_total",
	"status",
]

ORDER_FIELDS = [
	"name",
	"customer",
	"po_no",
	"transaction_date",
	"delivery_date",
	BRANCH_FIELD,
	"currency",
	"grand_total",
	"status",
	"per_delivered",
	"per_billed",
	"docstatus",
	FROM_PORTAL_FIELD,
	PORTAL_STATUS_FIELD,
]

PORTAL_ORDER_STATUS = {ORDER_PENDING: "Draft"}
AWAITING_CONFIRMATION = "Awaiting Confirmation"

DELIVERY_FIELDS = [
	"name",
	"customer",
	"po_no",
	"posting_date",
	"lr_no",
	"transporter_name",
	BRANCH_FIELD,
	"currency",
	"grand_total",
	"is_return",
	"status",
]

INVOICE_FIELDS = [
	"name",
	"customer",
	"po_no",
	"posting_date",
	"due_date",
	BRANCH_FIELD,
	"currency",
	"grand_total",
	"outstanding_amount",
	"is_return",
	"is_debit_note",
	"return_against",
	"status",
]


def customer_scope(customer: str | None = None) -> list[str]:
	return party_scope(CUSTOMER, customer)


def customer_filters(
	doctype: str,
	customers: list[str],
	branches: list[str] | None = None,
	user: str | None = None,
) -> list:
	if doctype == QUOTATION:
		return all_of(
			customer_scope_filters(QUOTATION, customers, "party_name", branches, user),
			{"quotation_to": CUSTOMER, "docstatus": 1},
		)

	return all_of(customer_scope_filters(doctype, customers, branches=branches, user=user), {"docstatus": 1})


def customer_document(doctype: str, name: str, customer: str | None = None):
	return owned_document(doctype, name, customer_filters(doctype, customer_scope(customer)))


def customer_documents(
	doctype: str,
	customers: list[str],
	search: str | None,
	fields: list[str],
	search_fields: tuple[str, ...] = ("name",),
	branches: list[str] | None = None,
	**filters,
) -> list:
	return find_documents(
		doctype,
		all_of(customer_filters(doctype, customers, branches), filters),
		search,
		fields,
		search_fields,
	)


def branch_statement_rows(customers: list[str]) -> Callable[[list[dict]], list[dict]] | None:
	limited = {customer for customer in branch_restrictions() if customer in customers}
	if not limited:
		return None

	def keep(rows: list[dict]) -> list[dict]:
		invoices = [
			row["voucher_no"]
			for row in rows
			if row.get("party") in limited and row.get("voucher_type") == SALES_INVOICE
		]
		visible = set(
			frappe.get_all(
				SALES_INVOICE,
				filters=all_of(
					customer_scope_filters(SALES_INVOICE, sorted(limited)),
					{"name": ("in", invoices or [""]), "docstatus": 1},
				),
				pluck="name",
			)
		)
		return [row for row in rows if row.get("party") not in limited or row["voucher_no"] in visible]

	return keep


@frappe.whitelist()
def get_quotations(
	customer: str | None = None,
	search: str | None = None,
	branches: list | str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	customers = customer_scope(customer)
	if not customers:
		return empty_page(start, limit)

	quotations = customer_documents(
		QUOTATION, customers, search, QUOTATION_FIELDS, branches=requested_branches(customers, branches)
	)

	return page_of(
		[
			{
				"name": quotation.name,
				"customer": quotation.party_name,
				"transaction_date": quotation.transaction_date,
				"valid_till": quotation.valid_till,
				"branch": quotation.get(BRANCH_FIELD),
				"currency": quotation.currency,
				"grand_total": quotation.grand_total,
				"status": quotation.status or "Open",
			}
			for quotation in quotations
		],
		start,
		limit,
	)


@frappe.whitelist()
def get_quotation(name: str, customer: str | None = None) -> dict:
	doc = customer_document(QUOTATION, name, customer)

	return {
		"name": doc.name,
		"customer": doc.party_name,
		"status": doc.status,
		"transaction_date": doc.transaction_date,
		"valid_till": doc.valid_till,
		"currency": doc.currency,
		"total": doc.total,
		"total_taxes": doc.total_taxes_and_charges,
		"grand_total": doc.grand_total,
		"terms": safe_html(doc.terms),
		"items": [line_item(item) for item in doc.items],
		"sales_orders": submitted_parents("Sales Order Item", "prevdoc_docname", doc.name),
	}


@frappe.whitelist()
def get_sales_orders(
	customer: str | None = None,
	search: str | None = None,
	branches: list | str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	customers = customer_scope(customer)
	if not customers:
		return empty_page(start, limit)

	orders = find_documents(
		SALES_ORDER,
		order_filters(customers, requested_branches(customers, branches)),
		search,
		ORDER_FIELDS,
		search_fields=("name", "po_no"),
	)

	return {
		**page_of(
			[
				{
					"name": order.name,
					"customer": order.customer,
					"po_no": order.po_no,
					"transaction_date": order.transaction_date,
					"delivery_date": order.delivery_date,
					"branch": order.get(BRANCH_FIELD),
					"currency": order.currency,
					"grand_total": order.grand_total,
					"delivered": flt(order.per_delivered, 1),
					"billed": flt(order.per_billed, 1),
					"status": order_status(order),
					"is_draft": order.docstatus == 0,
				}
				for order in orders
				if is_visible_order(order)
			],
			start,
			limit,
		),
		"can_order": can_order(customer),
	}


def order_filters(customers: list[str], branches: list[str] | None = None) -> list:
	return all_of(customer_scope_filters(SALES_ORDER, customers, branches=branches), {"docstatus": ("<", 2)})


def is_visible_order(order) -> bool:
	return order.docstatus == 1 or (order.docstatus == 0 and bool(order.get(FROM_PORTAL_FIELD)))


def order_status(order) -> str:
	if order.docstatus == 0:
		return PORTAL_ORDER_STATUS.get(order.get(PORTAL_STATUS_FIELD), AWAITING_CONFIRMATION)

	return order.status or "To Deliver and Bill"


def customer_order(name: str, customer: str | None = None):
	doc = owned_document(SALES_ORDER, name, order_filters(customer_scope(customer)))
	if not is_visible_order(doc):
		frappe.throw(_("This document does not belong to you."), frappe.PermissionError)

	return doc


@frappe.whitelist()
def get_sales_order(name: str, customer: str | None = None) -> dict:
	doc = customer_order(name, customer)

	items = [
		line_item(
			item,
			delivered_qty=flt(item.delivered_qty),
			outstanding_qty=max(flt(item.qty) - flt(item.delivered_qty), 0),
			delivery_date=item.delivery_date,
			quotation=item.prevdoc_docname,
		)
		for item in doc.items
	]

	return {
		"name": doc.name,
		"customer": doc.customer,
		"status": order_status(doc),
		"is_draft": doc.docstatus == 0,
		"editable": doc.docstatus == 0 and doc.get(PORTAL_STATUS_FIELD) == ORDER_PENDING,
		"withdrawable": doc.docstatus == 0 and doc.get(PORTAL_STATUS_FIELD) == ORDER_SUBMITTED,
		"po_no": doc.po_no,
		"po_date": doc.po_date,
		"transaction_date": doc.transaction_date,
		"delivery_date": doc.delivery_date,
		"currency": doc.currency,
		"total": doc.total,
		"grand_total": doc.grand_total,
		"delivered": flt(doc.per_delivered, 1),
		"billed": flt(doc.per_billed, 1),
		"shipping_address": safe_html(doc.shipping_address),
		"terms": safe_html(doc.terms),
		"quotations": distinct(items, "quotation"),
		"items": items,
		"deliveries": deliveries_against(doc.name),
		"invoices": submitted_parents("Sales Invoice Item", "sales_order", doc.name),
	}


def deliveries_against(order: str) -> list[dict]:
	names = submitted_parents("Delivery Note Item", "against_sales_order", order)
	if not names:
		return []

	return frappe.get_all(
		DELIVERY_NOTE,
		filters={"name": ("in", names), "docstatus": 1},
		fields=["name", "posting_date", "status", "is_return"],
		order_by="posting_date desc",
	)


@frappe.whitelist()
def get_delivery_notes(
	customer: str | None = None,
	search: str | None = None,
	branches: list | str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	customers = customer_scope(customer)
	if not customers:
		return empty_page(start, limit)

	deliveries = customer_documents(
		DELIVERY_NOTE,
		customers,
		search,
		DELIVERY_FIELDS,
		search_fields=("name", "po_no", "lr_no"),
		branches=requested_branches(customers, branches),
	)

	return page_of(
		[
			{
				"name": delivery.name,
				"customer": delivery.customer,
				"po_no": delivery.po_no,
				"posting_date": delivery.posting_date,
				"lr_no": delivery.lr_no,
				"transporter_name": delivery.transporter_name,
				"branch": delivery.get(BRANCH_FIELD),
				"currency": delivery.currency,
				"grand_total": delivery.grand_total,
				"is_return": bool(delivery.is_return),
				"status": delivery.status or "To Bill",
			}
			for delivery in deliveries
		],
		start,
		limit,
	)


@frappe.whitelist()
def get_delivery_note(name: str, customer: str | None = None) -> dict:
	doc = customer_document(DELIVERY_NOTE, name, customer)

	items = [
		line_item(item, returned_qty=flt(item.returned_qty), sales_order=item.against_sales_order)
		for item in doc.items
	]

	return {
		"name": doc.name,
		"customer": doc.customer,
		"status": doc.status,
		"is_return": bool(doc.is_return),
		"return_against": doc.return_against,
		"po_no": doc.po_no,
		"posting_date": doc.posting_date,
		"currency": doc.currency,
		"total": doc.total,
		"grand_total": doc.grand_total,
		"billed": flt(doc.per_billed, 1),
		"transporter_name": doc.transporter_name,
		"lr_no": doc.lr_no,
		"lr_date": doc.lr_date,
		"vehicle_no": doc.vehicle_no,
		"driver_name": doc.driver_name,
		"shipping_address": safe_html(doc.shipping_address),
		"terms": safe_html(doc.terms),
		"sales_orders": distinct(items, "sales_order"),
		"items": items,
		"invoices": submitted_parents("Sales Invoice Item", "delivery_note", doc.name),
	}


def date_range(from_date: str | None, to_date: str | None, field: str = "posting_date") -> dict:
	try:
		start = getdate(from_date) if from_date else None
		end = getdate(to_date) if to_date else None
	except Exception:
		frappe.throw(_("Pick the dates again. One of them could not be read."))

	if start and end and start > end:
		frappe.throw(_("The start date must be on or before the end date."))
	if start and end:
		return {field: ("between", [start, end])}
	if start:
		return {field: (">=", start)}
	if end:
		return {field: ("<=", end)}
	return {}


@frappe.whitelist()
def get_sales_invoices(
	customer: str | None = None,
	search: str | None = None,
	credit_notes: bool = False,
	branches: list | str | None = None,
	status: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	customers = customer_scope(customer)
	if not customers:
		return empty_page(start, limit)

	invoices = customer_documents(
		SALES_INVOICE,
		customers,
		search,
		INVOICE_FIELDS,
		search_fields=("name", "po_no"),
		branches=requested_branches(customers, branches),
		is_return=cint(credit_notes),
		**date_range(from_date, to_date),
	)

	rows = [
		{
			"name": invoice.name,
			"customer": invoice.customer,
			"po_no": invoice.po_no,
			"posting_date": invoice.posting_date,
			"due_date": invoice.due_date,
			"branch": invoice.get(BRANCH_FIELD),
			"currency": invoice.currency,
			"grand_total": invoice.grand_total,
			"outstanding_amount": invoice.outstanding_amount,
			"is_return": bool(invoice.is_return),
			"return_against": invoice.return_against,
			"is_debit_note": bool(invoice.is_debit_note),
			"status": invoice.status or "Unpaid",
		}
		for invoice in invoices
	]
	counts = dict(Counter(row["status"] for row in rows))

	return page_of(
		[row for row in rows if not status or row["status"] == status],
		start,
		limit,
		counts,
	)


@frappe.whitelist()
def get_sales_invoice(name: str, customer: str | None = None) -> dict:
	doc = customer_document(SALES_INVOICE, name, customer)

	items = [
		line_item(item, sales_order=item.sales_order, delivery_note=item.delivery_note) for item in doc.items
	]

	return {
		"name": doc.name,
		"customer": doc.customer,
		"status": doc.status,
		"is_return": bool(doc.is_return),
		"is_debit_note": bool(doc.is_debit_note),
		"return_against": doc.return_against,
		"po_no": doc.po_no,
		"posting_date": doc.posting_date,
		"due_date": doc.due_date,
		"currency": doc.currency,
		"total": doc.total,
		"total_taxes": doc.total_taxes_and_charges,
		"grand_total": doc.grand_total,
		"outstanding_amount": doc.outstanding_amount,
		"terms": safe_html(doc.terms),
		"sales_orders": distinct(items, "sales_order"),
		"delivery_notes": distinct(items, "delivery_note"),
		"items": items,
		"payments": payments_against(SALES_INVOICE, doc.name),
		"credit_notes": returns_against(SALES_INVOICE, doc.name),
		"credit_request": invoice_credit_state(doc),
	}


@frappe.whitelist()
def get_account_statement(customer: str | None = None, company: str | None = None) -> ApiResponse[dict]:
	customers = customer_scope(customer)
	return ApiResponse.success(
		data={
			**statement_page("Receivable", CUSTOMER, customers, company, branch_statement_rows(customers)),
			"branch_limited": any(customer in branch_restrictions() for customer in customers),
		}
	)


OPEN_ORDER_STATUSES = ("To Deliver and Bill", "To Deliver", "To Bill")
TO_DELIVER_STATUSES = ("To Deliver and Bill", "To Deliver")
QUOTES_TO_REVIEW = ("Open", "Replied")


@frappe.whitelist()
def get_dashboard(customer: str | None = None, branches: list | str | None = None) -> dict:
	customers = customer_scope(customer)
	if not customers:
		return {}

	branches = requested_branches(customers, branches)
	orders = customer_filters(SALES_ORDER, customers, branches)
	invoices = all_of(customer_filters(SALES_INVOICE, customers, branches), {"is_return": 0})
	quotes = frappe.get_all(
		QUOTATION,
		filters=all_of(
			customer_filters(QUOTATION, customers, branches), {"status": ("in", QUOTES_TO_REVIEW)}
		),
		or_filters=[["valid_till", ">=", nowdate()], ["valid_till", "is", "not set"]],
		fields=["name", "transaction_date", "valid_till", "grand_total", "currency"],
		order_by="valid_till asc",
	)
	open_orders = frappe.get_all(
		SALES_ORDER,
		filters=all_of(orders, {"status": ("in", OPEN_ORDER_STATUSES)}),
		fields=["name", "status", "delivery_date", "grand_total", "currency", "per_delivered"],
		order_by="delivery_date asc",
	)

	return {
		"currency": company_currency(),
		"quotes_to_review": len(quotes),
		"open_orders": len(open_orders),
		"balance": (
			None
			if branches
			else balance(
				outstanding_statement("Receivable", CUSTOMER, customers, branch_statement_rows(customers))
			)
		),
		"invoiced_by_month": monthly_totals(SALES_INVOICE, invoices, "posting_date", "base_grand_total"),
		"invoices_by_status": status_counts(SALES_INVOICE, invoices),
		"quotes": quotes[:5],
		"to_deliver": [
			{**order, "delivered": flt(order.per_delivered, 1)}
			for order in open_orders
			if order.status in TO_DELIVER_STATUSES
		][:5],
	}
