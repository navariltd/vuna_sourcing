# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from vuna_sourcing.utils import CUSTOMER, PARTY_TYPES, SUPPLIER, get_open_party_types

PARTY_ROLE = {SUPPLIER: "Supplier", CUSTOMER: "Customer"}


def get_current_user() -> str:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please sign in to use the portal."), frappe.PermissionError)

	return user


def get_linked_parties(user: str | None = None) -> list[dict]:
	user = user or get_current_user()
	roles = set(frappe.get_roles(user))

	portal_user = frappe.qb.DocType("Portal User")
	parties = []

	for party_type in PARTY_TYPES:
		if PARTY_ROLE[party_type] not in roles:
			continue

		names = (
			frappe.qb.from_(portal_user)
			.select(portal_user.parent)
			.where(portal_user.user == user)
			.where(portal_user.parenttype == party_type)
		).run(pluck=True)

		if not names:
			continue

		for record in frappe.get_all(
			party_type,
			filters={"name": ("in", names)},
			fields=["name", f"{party_type.lower()}_name as title", "image", "disabled"],
			order_by="modified desc",
		):
			parties.append(
				{
					"party_type": party_type,
					"name": record.name,
					"title": record.title or record.name,
					"image": record.image,
					"disabled": bool(record.disabled),
				}
			)

	return parties


def check_party_access(party_type: str, party: str, user: str | None = None):
	user = user or get_current_user()

	if party_type not in PARTY_TYPES:
		frappe.throw(_("{0} is not a portal party type.").format(party_type), frappe.PermissionError)

	allowed = any(p["party_type"] == party_type and p["name"] == party for p in get_linked_parties(user))
	if not allowed:
		frappe.throw(
			_("You do not have access to {0} {1}.").format(_(party_type), party),
			frappe.PermissionError,
		)


@frappe.whitelist()
def get_session() -> dict:
	user = get_current_user()

	profile = frappe.db.get_value(
		"User", user, ["full_name", "user_image", "email", "user_type"], as_dict=True
	)
	parties = get_linked_parties(user)
	roles = frappe.get_roles(user)
	open_party_types = get_open_party_types()

	return {
		"user": {
			"name": user,
			"full_name": profile.full_name,
			"email": profile.email,
			"image": profile.user_image,
			"is_website_user": profile.user_type == "Website User",
		},
		"parties": parties,
		"roles": roles,
		"open_party_types": open_party_types,
		"can_apply": bool(open_party_types),
		"is_applicant": not parties,
	}


@frappe.whitelist()
def get_party(party_type: str, party: str) -> dict:
	check_party_access(party_type, party)

	doc = frappe.get_doc(party_type, party)
	details = {
		"party_type": party_type,
		"name": doc.name,
		"title": doc.get(f"{party_type.lower()}_name") or doc.name,
		"image": doc.image,
		"disabled": bool(doc.disabled),
		"country": doc.get("country"),
		"default_currency": doc.get("default_currency"),
		"tax_id": doc.get("tax_id"),
		"website": doc.get("website"),
	}

	if party_type == SUPPLIER:
		details["group"] = doc.supplier_group
		details["entity_type"] = doc.supplier_type
	else:
		details["group"] = doc.customer_group
		details["entity_type"] = doc.customer_type
		details["territory"] = doc.territory

	return details
