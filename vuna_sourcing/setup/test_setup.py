# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime

from vuna_sourcing.api.permission import create_portal_user_role


def before_tests():
	frappe.clear_cache()

	if not frappe.db.a_row_exists("Company"):
		from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

		year = now_datetime().year
		setup_complete(
			{
				"currency": "KES",
				"full_name": "Test User",
				"company_name": "_Test Vuna Company",
				"timezone": "Africa/Nairobi",
				"company_abbr": "_TVC",
				"industry": "Manufacturing",
				"country": "Kenya",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@example.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)

		if not frappe.db.a_row_exists("Company"):
			frappe.throw(_("ERPNext setup wizard did not create a Company; see the Error Log for the cause."))

	create_portal_user_role()
	grant_supplier_portal_permissions()
	frappe.db.commit()  # nosemgrep


SUPPLIER_PORTAL_PERMISSIONS = {
	"Item": ("read",),
	"Account": ("select",),
	"Purchase Invoice": ("read", "select"),
	"Request for Quotation": ("read", "select"),
}


def grant_supplier_portal_permissions():
	"""Mirrors what a site grants the Supplier role in the desk, which a fresh CI site has not."""
	from frappe.permissions import add_permission, update_permission_property

	for doctype, rights in SUPPLIER_PORTAL_PERMISSIONS.items():
		add_permission(doctype, "Supplier", 0)

		for right in rights:
			update_permission_property(doctype, "Supplier", 0, right, 1)

		if "read" not in rights:
			update_permission_property(doctype, "Supplier", 0, "read", 0)
