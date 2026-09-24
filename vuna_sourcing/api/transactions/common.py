# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.html_utils import sanitize_html

from vuna_sourcing.api.portal import check_party_access, get_linked_parties


def my_parties(party_type: str, user: str | None = None) -> list[str]:
	return [party["name"] for party in get_linked_parties(user) if party["party_type"] == party_type]


def party_scope(party_type: str, party: str | None = None) -> list[str]:
	if not party:
		return my_parties(party_type)

	check_party_access(party_type, party)
	return [party]


def empty_page(start: int, limit: int) -> dict:
	return {"rows": [], "total": 0, "start": cint(start), "limit": cint(limit), "counts": {}}


def page_of(rows: list[dict], start: int, limit: int, counts: dict | None = None) -> dict:
	start = max(cint(start), 0)
	limit = max(cint(limit), 1)

	if counts is None:
		counts = dict(Counter(row["status"] for row in rows if row.get("status")))

	return {
		"rows": rows[start : start + limit],
		"total": len(rows),
		"start": start,
		"limit": limit,
		"counts": counts,
	}


def owned_document(doctype: str, name: str, filters: dict):
	mine = frappe.db.get_value(doctype, {**filters, "name": name}, "name")
	if not mine:
		frappe.throw(_("This document does not belong to you."), frappe.PermissionError)

	return frappe.get_doc(doctype, mine)


def find_documents(
	doctype: str,
	filters: dict,
	search: str | None,
	fields: list[str],
	search_fields: tuple[str, ...] = ("name",),
	order_by: str = "creation desc",
) -> list:
	or_filters = None
	if search and search.strip():
		pattern = f"%{search.strip()}%"
		or_filters = [[field, "like", pattern] for field in search_fields]

	return frappe.get_all(doctype, filters=filters, or_filters=or_filters, fields=fields, order_by=order_by)


def submitted_parents(child_doctype: str, link_field: str, name: str) -> list[str]:
	return list(
		dict.fromkeys(
			frappe.get_all(
				child_doctype,
				filters={link_field: name, "docstatus": 1},
				pluck="parent",
				order_by="creation desc",
			)
		)
	)


def distinct(rows: list[dict], key: str) -> list[str]:
	return sorted({row[key] for row in rows if row.get(key)})


def payments_against(doctype: str, name: str) -> list[dict]:
	references = frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_doctype": doctype, "reference_name": name, "docstatus": 1},
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


def line_item(item, **extra) -> dict:
	return {
		"name": item.name,
		"item_code": item.item_code,
		**item_description(item),
		"qty": item.qty,
		"uom": item.uom,
		"rate": item.rate,
		"amount": item.amount,
		**extra,
	}
