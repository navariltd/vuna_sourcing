# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe

DESK_ROLES = (
	"Purchase User",
	"Purchase Master Manager",
	"Sales User",
	"Sales Master Manager",
	"System Manager",
)

PORTAL_USER_ROLE = "Sourcing Portal User"

PORTAL_ROLES = ("Supplier", "Customer", PORTAL_USER_ROLE)


def create_portal_user_role() -> None:
	if not frappe.db.exists("Role", PORTAL_USER_ROLE):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": PORTAL_USER_ROLE,
				"desk_access": 0,
				"home_page": "/vuna-sourcing",
			}
		).insert(ignore_permissions=True)


def has_app_permission() -> bool:
	user = frappe.session.user
	if not user or user == "Guest":
		return False

	roles = set(frappe.get_roles(user))
	return bool(roles.intersection(DESK_ROLES) or roles.intersection(PORTAL_ROLES))
