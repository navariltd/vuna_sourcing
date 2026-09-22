# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.utils.rename_field import rename_field

from vuna_sourcing.install import apply_single_defaults

REQUEST = "Party Onboarding Request"
TEMPLATE = "Party Onboarding Template"


def execute():
	apply_single_defaults("Sourcing Settings")

	for doctype, old, new in (
		(REQUEST, "supplier_name", "party_name"),
		(REQUEST, "supplier_type", "entity_type"),
		(REQUEST, "supplier", "party"),
		(TEMPLATE, "supplier_type", "entity_type"),
	):
		if frappe.db.has_column(doctype, old):
			rename_field(doctype, old, new)

	for doctype in (REQUEST, TEMPLATE):
		frappe.db.set_value(
			doctype, {"party_type": ("is", "not set")}, "party_type", "Supplier", update_modified=False
		)

	frappe.db.set_value(
		"Party Document Type",
		{"applies_to": ("is", "not set")},
		"applies_to",
		"Supplier and Customer",
		update_modified=False,
	)

	if frappe.db.has_column(REQUEST, "contact_first_name"):
		move_contacts_and_addresses()


def old_columns(*names):
	return [name for name in names if frappe.db.has_column(REQUEST, name)]


def move_contacts_and_addresses():
	columns = old_columns(
		"contact_first_name",
		"contact_last_name",
		"designation",
		"email_id",
		"mobile_no",
		"contact",
		"use_separate_billing_contact",
		"billing_contact_first_name",
		"billing_contact_last_name",
		"billing_email_id",
		"billing_mobile_no",
		"billing_contact",
		"address_line1",
		"address_line2",
		"city",
		"state",
		"pincode",
		"address_country",
		"address",
	)
	table = frappe.qb.DocType(REQUEST)
	rows = frappe.qb.from_(table).select(table.name, *(table[c] for c in columns)).run(as_dict=True)

	for old in rows:
		if frappe.db.exists("Party Onboarding Contact", {"parent": old.name}) or frappe.db.exists(
			"Party Onboarding Address", {"parent": old.name}
		):
			continue

		contacts = []
		if old.get("contact_first_name") or old.get("email_id"):
			contacts.append(
				{
					"first_name": old.get("contact_first_name"),
					"last_name": old.get("contact_last_name"),
					"designation": old.get("designation"),
					"email_id": old.get("email_id"),
					"mobile_no": old.get("mobile_no"),
					"is_primary_contact": 1,
					"is_billing_contact": 0 if old.get("use_separate_billing_contact") else 1,
					"contact": old.get("contact"),
				}
			)
		if old.get("use_separate_billing_contact") and (
			old.get("billing_contact_first_name") or old.get("billing_email_id")
		):
			contacts.append(
				{
					"first_name": old.get("billing_contact_first_name"),
					"last_name": old.get("billing_contact_last_name"),
					"email_id": old.get("billing_email_id"),
					"mobile_no": old.get("billing_mobile_no"),
					"is_billing_contact": 1,
					"contact": old.get("billing_contact"),
				}
			)

		addresses = []
		if old.get("address_line1") or old.get("city"):
			addresses.append(
				{
					"address_type": "Billing",
					"address_line1": old.get("address_line1"),
					"address_line2": old.get("address_line2"),
					"city": old.get("city"),
					"state": old.get("state"),
					"pincode": old.get("pincode"),
					"country": old.get("address_country"),
					"is_primary_address": 1,
					"address": old.get("address"),
				}
			)

		for table, doctype, values in (
			("contacts", "Party Onboarding Contact", contacts),
			("addresses", "Party Onboarding Address", addresses),
		):
			for idx, row in enumerate(values, start=1):
				frappe.get_doc(
					{
						"doctype": doctype,
						"parent": old.name,
						"parenttype": REQUEST,
						"parentfield": table,
						"idx": idx,
						**row,
					}
				).db_insert()
