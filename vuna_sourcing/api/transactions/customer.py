# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from vuna_sourcing.api.transactions.common import (
	distinct,
	empty_page,
	find_documents,
	line_item,
	owned_document,
	page_of,
	party_scope,
	payments_against,
	safe_html,
	submitted_parents,
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
	"currency",
	"grand_total",
	"status",
	"per_delivered",
	"per_billed",
]

DELIVERY_FIELDS = [
	"name",
	"customer",
	"po_no",
	"posting_date",
	"lr_no",
	"transporter_name",
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
	"currency",
	"grand_total",
	"outstanding_amount",
	"is_return",
	"status",
]


def customer_scope(customer: str | None = None) -> list[str]:
	return party_scope(CUSTOMER, customer)


def customer_filters(doctype: str, customers: list[str]) -> dict:
	if doctype == QUOTATION:
		return {"quotation_to": CUSTOMER, "party_name": ("in", customers or [""]), "docstatus": 1}

	return {"customer": ("in", customers or [""]), "docstatus": 1}


def customer_document(doctype: str, name: str, customer: str | None = None):
	return owned_document(doctype, name, customer_filters(doctype, customer_scope(customer)))


def customer_documents(
	doctype: str,
	customers: list[str],
	search: str | None,
	fields: list[str],
	search_fields: tuple[str, ...] = ("name",),
) -> list:
	return find_documents(doctype, customer_filters(doctype, customers), search, fields, search_fields)


@frappe.whitelist()
def get_quotations(
	customer: str | None = None,
	search: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	customers = customer_scope(customer)
	if not customers:
		return empty_page(start, limit)

	quotations = customer_documents(QUOTATION, customers, search, QUOTATION_FIELDS)

	return page_of(
		[
			{
				"name": quotation.name,
				"customer": quotation.party_name,
				"transaction_date": quotation.transaction_date,
				"valid_till": quotation.valid_till,
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
	start: int = 0,
	limit: int = 20,
) -> dict:
	customers = customer_scope(customer)
	if not customers:
		return empty_page(start, limit)

	orders = customer_documents(SALES_ORDER, customers, search, ORDER_FIELDS, search_fields=("name", "po_no"))

	return page_of(
		[
			{
				"name": order.name,
				"customer": order.customer,
				"po_no": order.po_no,
				"transaction_date": order.transaction_date,
				"delivery_date": order.delivery_date,
				"currency": order.currency,
				"grand_total": order.grand_total,
				"delivered": flt(order.per_delivered, 1),
				"billed": flt(order.per_billed, 1),
				"status": order.status or "To Deliver and Bill",
			}
			for order in orders
		],
		start,
		limit,
	)


@frappe.whitelist()
def get_sales_order(name: str, customer: str | None = None) -> dict:
	doc = customer_document(SALES_ORDER, name, customer)

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
		"status": doc.status,
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
	start: int = 0,
	limit: int = 20,
) -> dict:
	customers = customer_scope(customer)
	if not customers:
		return empty_page(start, limit)

	deliveries = customer_documents(
		DELIVERY_NOTE, customers, search, DELIVERY_FIELDS, search_fields=("name", "po_no", "lr_no")
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


@frappe.whitelist()
def get_sales_invoices(
	customer: str | None = None,
	search: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	customers = customer_scope(customer)
	if not customers:
		return empty_page(start, limit)

	invoices = customer_documents(
		SALES_INVOICE, customers, search, INVOICE_FIELDS, search_fields=("name", "po_no")
	)

	return page_of(
		[
			{
				"name": invoice.name,
				"customer": invoice.customer,
				"po_no": invoice.po_no,
				"posting_date": invoice.posting_date,
				"due_date": invoice.due_date,
				"currency": invoice.currency,
				"grand_total": invoice.grand_total,
				"outstanding_amount": invoice.outstanding_amount,
				"is_return": bool(invoice.is_return),
				"status": invoice.status or "Unpaid",
			}
			for invoice in invoices
		],
		start,
		limit,
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
	}
