# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.permissions import add_permission, update_permission_property

from vuna_sourcing.api.permission import create_portal_user_role
from vuna_sourcing.api.portal import PARTY_ROLE
from vuna_sourcing.api.transactions.customer import DELIVERY_NOTE, QUOTATION, SALES_INVOICE, SALES_ORDER
from vuna_sourcing.api.transactions.rights import CREATE, DELETE, PRINT, READ, WRITE
from vuna_sourcing.api.transactions.supplier import (
	PURCHASE_INVOICE,
	PURCHASE_ORDER,
	RFQ,
	SUPPLIER_QUOTATION,
)
from vuna_sourcing.utils import CUSTOMER, SUPPLIER

CUSTOM_DOCPERM = "Custom DocPerm"
APPLIED_PERMISSIONS_KEY = "vuna_sourcing_portal_permissions"

VIEW_AND_PRINT = (READ, PRINT)
MANAGE_DRAFTS = (READ, PRINT, CREATE, WRITE, DELETE)

PORTAL_PERMISSION_DEFAULTS = {
	PARTY_ROLE[CUSTOMER]: {
		QUOTATION: VIEW_AND_PRINT,
		SALES_ORDER: MANAGE_DRAFTS,
		DELIVERY_NOTE: VIEW_AND_PRINT,
		SALES_INVOICE: VIEW_AND_PRINT,
	},
	PARTY_ROLE[SUPPLIER]: {
		RFQ: VIEW_AND_PRINT,
		SUPPLIER_QUOTATION: MANAGE_DRAFTS,
		PURCHASE_ORDER: VIEW_AND_PRINT,
		PURCHASE_INVOICE: VIEW_AND_PRINT,
	},
}


def after_install() -> None:
	create_portal_user_role()
	apply_portal_permission_defaults()


def after_migrate() -> None:
	create_portal_user_role()
	apply_portal_permission_defaults()


def applied_permission_defaults() -> set[str]:
	try:
		return set(json.loads(frappe.db.get_global(APPLIED_PERMISSIONS_KEY) or "[]"))
	except ValueError:
		return set()


def apply_portal_permission_defaults() -> None:
	applied = applied_permission_defaults()
	pending = [
		(role, doctype, rights)
		for role, doctypes in PORTAL_PERMISSION_DEFAULTS.items()
		for doctype, rights in doctypes.items()
		if f"{doctype}::{role}" not in applied and frappe.db.exists("Role", role)
	]
	if not pending:
		return

	for role, doctype, rights in pending:
		grant(doctype, role, rights)
		applied.add(f"{doctype}::{role}")

	frappe.db.set_global(APPLIED_PERMISSIONS_KEY, json.dumps(sorted(applied)))
	frappe.clear_cache()


def grant(doctype: str, role: str, rights: tuple[str, ...]) -> None:
	if not frappe.db.exists(CUSTOM_DOCPERM, {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}):
		add_permission(doctype, role, 0)

	for right in rights:
		update_permission_property(doctype, role, 0, right, 1, validate=False)
