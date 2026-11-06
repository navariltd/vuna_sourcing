# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe

from vuna_sourcing import APP_NAME

DESK_ROLES = (
	"Purchase User",
	"Purchase Master Manager",
	"Sales User",
	"Sales Master Manager",
	"System Manager",
)

PORTAL_USER_ROLE = "Sourcing Portal User"

PORTAL_ROLES = ("Supplier", "Customer", PORTAL_USER_ROLE)

PORTAL_HOME_PAGE = "vuna-sourcing"
WEBSITE_USER = "Website User"


def create_portal_user_role() -> None:
	if not frappe.db.exists("Role", PORTAL_USER_ROLE):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": PORTAL_USER_ROLE,
				"desk_access": 0,
			}
		).insert(ignore_permissions=True)  # nosemgrep
	elif frappe.db.get_value("Role", PORTAL_USER_ROLE, "home_page"):
		frappe.db.set_value("Role", PORTAL_USER_ROLE, "home_page", None)


def portal_home_page(user: str) -> str | None:
	if not user or user == "Guest":
		return None

	if frappe.get_cached_value("User", user, "user_type") != WEBSITE_USER:
		return None

	return PORTAL_HOME_PAGE if set(frappe.get_roles(user)).intersection(PORTAL_ROLES) else None


def clear_portal_default_app(login_manager=None) -> None:
	user = frappe.session.user
	if user in ("Guest", "Administrator") or has_app_permission():
		return

	if frappe.db.get_value("User", user, "default_app") == APP_NAME:
		frappe.db.set_value("User", user, "default_app", None, update_modified=False)


def has_app_permission() -> bool:
	user = frappe.session.user
	if not user or user == "Guest":
		return False

	return bool(set(frappe.get_roles(user)).intersection(DESK_ROLES))
