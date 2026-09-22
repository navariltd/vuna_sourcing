# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe

RENAMES = (
	("Supplier Document Type", "Party Document Type"),
	("Supplier Onboarding Document Requirement", "Party Onboarding Document Requirement"),
	("Supplier Onboarding Request Document", "Party Onboarding Request Document"),
	("Supplier Onboarding Template", "Party Onboarding Template"),
	("Supplier Onboarding Request", "Party Onboarding Request"),
)


def execute():
	for old, new in RENAMES:
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True)
