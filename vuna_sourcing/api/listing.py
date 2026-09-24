# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe.utils import cint

from vuna_sourcing.api.portal import check_party_access, get_linked_parties
from vuna_sourcing.utils import SUPPLIER


def my_suppliers(user: str | None = None) -> list[str]:
	return [party["name"] for party in get_linked_parties(user) if party["party_type"] == SUPPLIER]


def supplier_scope(supplier: str | None = None) -> list[str]:
	if not supplier:
		return my_suppliers()

	check_party_access(SUPPLIER, supplier)
	return [supplier]


def empty_page(start: int, limit: int) -> dict:
	return {"rows": [], "total": 0, "start": cint(start), "limit": cint(limit), "counts": {}}


def page_of(rows: list[dict], start: int, limit: int) -> dict:
	start = max(cint(start), 0)
	limit = max(cint(limit), 1)

	return {
		"rows": rows[start : start + limit],
		"total": len(rows),
		"start": start,
		"limit": limit,
		"counts": dict(Counter(row["status"] for row in rows if row.get("status"))),
	}


def my_document(doctype: str, name: str, supplier: str | None = None):
	from frappe import _

	suppliers = supplier_scope(supplier)
	mine = frappe.db.get_value(
		doctype,
		{"name": name, "supplier": ("in", suppliers or [""]), "docstatus": ("<", 2)},
		"name",
	)
	if not mine:
		frappe.throw(_("This document does not belong to you."), frappe.PermissionError)

	return frappe.get_doc(doctype, mine)


def party_documents(doctype: str, suppliers: list[str], search: str | None, fields: list[str]) -> list:
	filters = {"supplier": ("in", suppliers), "docstatus": ("<", 2)}
	if search:
		filters["name"] = ("like", f"%{search.strip()}%")

	return frappe.get_all(doctype, filters=filters, fields=fields, order_by="creation desc")
