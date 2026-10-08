# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from dataclasses import dataclass

import frappe
from frappe import _

from vuna_sourcing import APP_NAME

SUPPLIER = "Supplier"
CUSTOMER = "Customer"
PARTY_TYPES = (SUPPLIER, CUSTOMER)


@dataclass(frozen=True)
class PartySpec:
	doctype: str
	name_field: str
	entity_field: str
	group_field: str
	group_doctype: str
	primary_contact_field: str
	primary_address_field: str
	reviewer_roles: tuple[str, ...]
	accepts_setting: str


PARTY_SPECS = {
	SUPPLIER: PartySpec(
		doctype="Supplier",
		name_field="supplier_name",
		entity_field="supplier_type",
		group_field="supplier_group",
		group_doctype="Supplier Group",
		primary_contact_field="supplier_primary_contact",
		primary_address_field="supplier_primary_address",
		reviewer_roles=("Purchase Master Manager",),
		accepts_setting="accept_supplier_applications",
	),
	CUSTOMER: PartySpec(
		doctype="Customer",
		name_field="customer_name",
		entity_field="customer_type",
		group_field="customer_group",
		group_doctype="Customer Group",
		primary_contact_field="customer_primary_contact",
		primary_address_field="customer_primary_address",
		reviewer_roles=("Sales Master Manager",),
		accepts_setting="accept_customer_applications",
	),
}


def get_party_spec(party_type: str | None) -> PartySpec:
	if party_type not in PARTY_SPECS:
		frappe.throw(
			_("{0} is not a party that can be onboarded. Choose Supplier or Customer.").format(
				frappe.bold(party_type or _("(blank)"))
			),
			title=_("Invalid Party Type"),
		)
	return PARTY_SPECS[party_type]


def get_open_party_types() -> list[str]:
	settings = frappe.get_cached_doc("Sourcing Settings")
	return [party_type for party_type, spec in PARTY_SPECS.items() if settings.get(spec.accepts_setting)]


def get_app_branding() -> dict:
	entry = (frappe.get_hooks("add_to_apps_screen", app_name=APP_NAME) or [{}])[0]

	def first(hook: str) -> str | None:
		values = frappe.get_hooks(hook, app_name=APP_NAME)
		return values[0] if values else None

	return {
		"name": APP_NAME,
		"title": entry.get("title") or first("app_title"),
		"logo": entry.get("logo"),
		"publisher": first("app_publisher"),
	}


@frappe.whitelist()
def get_entity_type_options(party_type: str = SUPPLIER) -> list[str]:
	spec = get_party_spec(party_type)
	field = frappe.get_meta(spec.doctype).get_field(spec.entity_field)
	if not (field and field.options):
		return []

	return [option.strip() for option in field.options.split("\n") if option.strip()]


def validate_entity_type(party_type: str | None, value: str | None, label: str | None = None):
	if not (value and party_type):
		return

	options = get_entity_type_options(party_type)
	if not options or value in options:
		return

	frappe.throw(
		_("{0} must be one of {1}, because that is what a {2} accepts.").format(
			frappe.bold(label or _("Entity Type")),
			", ".join(frappe.bold(option) for option in options),
			_(party_type),
		),
		title=_("Invalid Entity Type"),
	)
