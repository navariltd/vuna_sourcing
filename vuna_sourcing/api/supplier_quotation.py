# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _
from frappe.utils import cint

from vuna_sourcing.api.listing import empty_page, my_suppliers, supplier_scope
from vuna_sourcing.api.portal import check_party_access
from vuna_sourcing.api.rfq import QUOTE, QUOTE_ITEM, item_description, safe_html


def status_of(row) -> str:
	return row.get("status") or ("Submitted" if row.get("docstatus") == 1 else "Draft")


def my_quotation(name: str, supplier: str | None = None) -> dict:
	suppliers = supplier_scope(supplier)

	quotation = frappe.db.get_value(
		QUOTE,
		{"name": name, "supplier": ("in", suppliers or [""]), "docstatus": ("<", 2)},
		"name",
	)
	if not quotation:
		frappe.throw(_("This quotation does not belong to you."), frappe.PermissionError)

	return frappe.get_doc(QUOTE, quotation)


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

	filters = {"supplier": ("in", suppliers), "docstatus": ("<", 2)}
	if search:
		filters["name"] = ("like", f"%{search.strip()}%")

	quotations = frappe.get_all(
		QUOTE,
		filters=filters,
		fields=[
			"name",
			"supplier",
			"transaction_date",
			"valid_till",
			"quotation_number",
			"total",
			"currency",
			"status",
			"docstatus",
		],
		order_by="transaction_date desc, creation desc",
	)
	if not quotations:
		return empty_page(start, limit)

	answered = {}
	counts = Counter()
	for row in frappe.get_all(
		QUOTE_ITEM,
		filters={"parent": ("in", [quotation.name for quotation in quotations])},
		fields=["parent", "request_for_quotation"],
	):
		counts[row.parent] += 1
		if row.request_for_quotation:
			answered.setdefault(row.parent, row.request_for_quotation)

	listing = [
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
			"status": status_of(quotation),
		}
		for quotation in quotations
	]

	by_status = Counter(row["status"] for row in listing)
	start = max(cint(start), 0)
	limit = max(cint(limit), 1)

	return {
		"rows": listing[start : start + limit],
		"total": len(listing),
		"start": start,
		"limit": limit,
		"counts": dict(by_status),
	}


@frappe.whitelist()
def get_supplier_quotation(name: str, supplier: str | None = None) -> dict:
	doc = my_quotation(name, supplier)

	items = []
	for item in doc.items:
		described = item_description(item)
		items.append(
			{
				"name": item.name,
				"item_code": item.item_code,
				"item_name": described.get("item_name"),
				"description": described.get("description"),
				"qty": item.qty,
				"uom": item.uom,
				"rate": item.rate,
				"amount": item.amount,
				"lead_time_days": item.lead_time_days,
				"rfq": item.request_for_quotation,
			}
		)

	return {
		"name": doc.name,
		"supplier": doc.supplier,
		"status": status_of(doc),
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
