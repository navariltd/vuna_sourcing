# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.permissions import get_valid_perms

from vuna_sourcing.api.permission import PORTAL_ROLES
from vuna_sourcing.api.transactions.common import my_parties
from vuna_sourcing.api.transactions.customer import (
	DELIVERY_NOTE,
	QUOTATION,
	SALES_INVOICE,
	SALES_ORDER,
	customer_filters,
)
from vuna_sourcing.api.transactions.supplier import (
	PURCHASE_INVOICE,
	PURCHASE_ORDER,
	RFQ,
	RFQ_SUPPLIER,
	SUPPLIER_QUOTATION,
	supplier_filters,
)
from vuna_sourcing.utils import CUSTOMER, SUPPLIER

CUSTOMER_DOCTYPES = (QUOTATION, SALES_ORDER, DELIVERY_NOTE, SALES_INVOICE)
SUPPLIER_DOCTYPES = (RFQ, SUPPLIER_QUOTATION, PURCHASE_ORDER, PURCHASE_INVOICE)
PORTAL_DOCTYPES = CUSTOMER_DOCTYPES + SUPPLIER_DOCTYPES

NOT_STAFF_ROLES = {*PORTAL_ROLES, "All", "Guest"}


def is_staff(doctype: str, user: str) -> bool:
	return any(
		perm.role not in NOT_STAFF_ROLES and not perm.permlevel and (perm.read or perm.print)
		for perm in get_valid_perms(doctype, user)
	)


def as_list(filters: dict) -> list[list]:
	return [
		[field, *value] if isinstance(value, tuple) else [field, "=", value]
		for field, value in filters.items()
	]


def party_filters(doctype: str, user: str) -> list[list]:
	if doctype in CUSTOMER_DOCTYPES:
		return as_list(customer_filters(doctype, my_parties(CUSTOMER, user)))

	suppliers = my_parties(SUPPLIER, user)
	if doctype == RFQ:
		return [[RFQ_SUPPLIER, "supplier", "in", suppliers or [""]], ["docstatus", "=", 1]]

	return as_list(supplier_filters(suppliers))


def is_own_document(doc, ptype: str | None = None, user: str | None = None, **kwargs) -> bool:
	user = user or frappe.session.user
	if user == "Administrator" or is_staff(doc.doctype, user):
		return True

	if not doc.name:
		return False

	return bool(
		frappe.get_all(
			doc.doctype,
			filters=[*party_filters(doc.doctype, user), ["name", "=", doc.name]],
			limit=1,
			pluck="name",
		)
	)


def own_documents_condition(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if doctype not in PORTAL_DOCTYPES or user == "Administrator" or is_staff(doctype, user):
		return ""

	mine = frappe.get_all(doctype, filters=party_filters(doctype, user), pluck="name", distinct=True, run=0)
	return f"`tab{doctype}`.`name` in ({mine})"
