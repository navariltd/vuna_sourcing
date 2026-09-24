# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import formatdate

from vuna_sourcing.api.listing import (
	empty_page,
	my_document,
	page_of,
	party_documents,
	supplier_scope,
)
from vuna_sourcing.api.rfq import safe_html

INVOICE = "Purchase Invoice"

FIELDS = [
	"name",
	"supplier",
	"posting_date",
	"due_date",
	"bill_no",
	"currency",
	"grand_total",
	"outstanding_amount",
	"status",
]


@frappe.whitelist()
def get_purchase_invoices(
	supplier: str | None = None,
	search: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> dict:
	suppliers = supplier_scope(supplier)
	if not suppliers:
		return empty_page(start, limit)

	invoices = party_documents(INVOICE, suppliers, search, FIELDS)

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
				"status": invoice.status or "Unpaid",
			}
			for invoice in invoices
		],
		start,
		limit,
	)


@frappe.whitelist()
def get_purchase_invoice(name: str, supplier: str | None = None) -> dict:
	print("dddd", name, supplier)
	doc = my_document(INVOICE, name, supplier)

	items = [
		{
			"name": item.name,
			"item_code": item.item_code,
			"item_name": item.item_name or item.item_code,
			"description": item.description,
			"qty": item.qty,
			"uom": item.uom,
			"rate": item.rate,
			"amount": item.amount,
			"purchase_order": item.purchase_order,
		}
		for item in doc.items
	]

	return {
		"name": doc.name,
		"supplier": doc.supplier,
		"status": doc.status,
		"bill_no": doc.bill_no,
		"bill_date": doc.bill_date,
		"posting_date": doc.posting_date,
		"due_date": doc.due_date,
		"currency": doc.currency,
		"total": doc.total,
		"grand_total": doc.grand_total,
		"outstanding_amount": doc.outstanding_amount,
		"on_hold": bool(doc.on_hold),
		"hold_reason": hold_reason(doc),
		"terms": safe_html(doc.terms),
		"purchase_orders": sorted({item["purchase_order"] for item in items if item["purchase_order"]}),
		"items": items,
		"payments": payments_against(doc.name),
	}


def hold_reason(doc) -> str | None:
	if not doc.on_hold:
		return None

	if doc.release_date:
		return _("On hold until {0}").format(formatdate(doc.release_date))

	return _("On hold")


def payments_against(invoice: str) -> list[dict]:
	references = frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_doctype": INVOICE, "reference_name": invoice, "docstatus": 1},
		fields=["parent", "allocated_amount"],
	)
	if not references:
		return []

	allocated = {row.parent: row.allocated_amount for row in references}
	entries = frappe.get_all(
		"Payment Entry",
		filters={"name": ("in", list(allocated)), "docstatus": 1},
		fields=["name", "posting_date", "mode_of_payment", "reference_no", "paid_amount"],
		order_by="posting_date desc",
	)

	return [
		{
			"name": entry.name,
			"posting_date": entry.posting_date,
			"mode_of_payment": entry.mode_of_payment,
			"reference_no": entry.reference_no,
			"allocated_amount": allocated.get(entry.name),
		}
		for entry in entries
	]
