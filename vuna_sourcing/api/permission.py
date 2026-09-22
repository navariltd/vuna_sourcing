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

PORTAL_ROLES = ("Supplier", "Customer")


def has_app_permission() -> bool:
	user = frappe.session.user
	if not user or user == "Guest":
		return False

	roles = set(frappe.get_roles(user))
	return bool(roles.intersection(DESK_ROLES) or roles.intersection(PORTAL_ROLES))
