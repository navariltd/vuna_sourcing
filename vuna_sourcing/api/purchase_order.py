# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from vuna_sourcing.api.listing import (
	empty_page,
	my_document,
	page_of,
	party_documents,
	supplier_scope,
)
from vuna_sourcing.api.rfq import safe_html

ORDER = "Purchase Order"

FIELDS = [
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

	orders = party_documents(ORDER, suppliers, search, FIELDS)

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
	doc = my_document(ORDER, name, supplier)

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
			"received_qty": flt(item.received_qty),
			"outstanding_qty": max(flt(item.qty) - flt(item.received_qty), 0),
			"required_by": item.schedule_date,
		}
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
