# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe

from vuna_sourcing.api.permission import create_portal_user_role


def after_install() -> None:
	create_portal_user_role()
	apply_single_defaults("Sourcing Settings")


def apply_single_defaults(doctype: str):
	stored = set(frappe.db.sql_list("select field from `tabSingles` where doctype = %s", doctype))
	missing = {
		df.fieldname: df.default
		for df in frappe.get_meta(doctype).fields
		if df.default is not None and df.fieldname not in stored
	}
	if missing:
		frappe.db.set_single_value(doctype, missing)
		frappe.clear_document_cache(doctype, doctype)
