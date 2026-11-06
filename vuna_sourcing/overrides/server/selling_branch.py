# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint

from vuna_sourcing.api.transactions.branches import BRANCH_FIELD, BRANCHES_FIELD, PORTAL_USER
from vuna_sourcing.utils import CUSTOMER

QUOTATION = "Quotation"
SETTING = "require_branch_for_branch_customers"


def billed_customer(doc) -> str | None:
	if doc.doctype == QUOTATION:
		return doc.party_name if doc.quotation_to == CUSTOMER else None

	return doc.get("customer")


def has_branch_users(customer: str) -> bool:
	return bool(
		frappe.db.exists(
			PORTAL_USER,
			{"parenttype": CUSTOMER, "parent": customer, BRANCHES_FIELD: ("is", "set")},
		)
	)


def validate_branch(doc, method: str | None = None) -> None:
	customer = billed_customer(doc)
	if not customer or doc.get(BRANCH_FIELD):
		return

	if not cint(frappe.db.get_single_value("Sourcing Settings", SETTING)) or not has_branch_users(customer):
		return

	frappe.throw(
		_(
			"{0} has portal users who only see some branches. Set the Shipping Address so the right branch can see this {1}."
		).format(frappe.bold(customer), _(doc.doctype)),
		title=_("Shipping Address Required"),
	)
