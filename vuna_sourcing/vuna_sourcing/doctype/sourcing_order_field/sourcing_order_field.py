# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from vuna_sourcing.dynamic_fields import (
	DATE,
	LONG_TEXT,
	MULTIPLE_CHOICE,
	NUMBER,
	SHORT_TEXT,
	WHOLE_NUMBER,
	choices_of,
	clean_value,
	is_blank,
)

SETTINGS = "Sourcing Settings"
TABLE_FIELD = "portal_order_fields"
SALES_ORDER = "Sales Order"
SYSTEM_MANAGER = "System Manager"

PORTAL_MANAGED_FIELDS = frozenset({"created_from_portal", "portal_submission_status", "portal_po_document"})

FIELD_TYPES = {
	"Data": SHORT_TEXT,
	"Small Text": LONG_TEXT,
	"Text": LONG_TEXT,
	"Long Text": LONG_TEXT,
	"Int": WHOLE_NUMBER,
	"Float": NUMBER,
	"Currency": NUMBER,
	"Percent": NUMBER,
	"Date": DATE,
	"Select": MULTIPLE_CHOICE,
}


class SourcingOrderField(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		field_type: DF.Data | None
		fieldname: DF.Literal[None]
		label: DF.Data | None
		mandatory: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types

	pass


def is_eligible(df) -> bool:
	return bool(
		df.get("is_custom_field")
		and df.fieldtype in FIELD_TYPES
		and df.fieldname not in PORTAL_MANAGED_FIELDS
		and not df.get("read_only")
		and not df.get("fetch_from")
		and not df.get("is_virtual")
	)


def field_definition(df) -> dict:
	field_type = FIELD_TYPES[df.fieldtype]
	return {
		"fieldname": df.fieldname,
		"label": df.label or df.fieldname,
		"fieldtype": df.fieldtype,
		"field_type": field_type,
		"description": df.description or None,
		"choices": choices_of(field_type, df.options),
	}


def eligible_fields() -> dict[str, dict]:
	return {
		df.fieldname: field_definition(df) for df in frappe.get_meta(SALES_ORDER).fields if is_eligible(df)
	}


@frappe.whitelist()
def get_sales_order_fields() -> list[dict]:
	frappe.only_for(SYSTEM_MANAGER)
	return list(eligible_fields().values())


def validate_order_fields(settings) -> None:
	available = eligible_fields()
	chosen = set()

	for row in settings.get(TABLE_FIELD) or []:
		field = available.get(row.fieldname)
		if not field:
			frappe.throw(
				_(
					"Row #{0}: {1} is not a custom Sales Order field the portal can fill in. Pick a custom field of type Data, Text, Int, Float, Currency, Percent, Date or Select that is not read-only."
				).format(row.idx, frappe.bold(row.fieldname or _("(empty)"))),
				title=_("Unsupported Order Field"),
			)
		if row.fieldname in chosen:
			frappe.throw(
				_("Row #{0}: {1} is already in the list.").format(row.idx, frappe.bold(field["label"])),
				title=_("Duplicate Order Field"),
			)
		if field["field_type"] == MULTIPLE_CHOICE and not field["choices"]:
			frappe.throw(
				_("Row #{0}: give {1} its options on the Sales Order field first.").format(
					row.idx, frappe.bold(field["label"])
				),
				title=_("Choices Needed"),
			)
		chosen.add(row.fieldname)
		row.label = field["label"]
		row.field_type = field["field_type"]
		row.description = (row.description or "").strip() or None


def portal_order_fields() -> list[dict]:
	available = eligible_fields()
	return [
		{
			"fieldname": row.fieldname,
			"label": available[row.fieldname]["label"],
			"field_type": available[row.fieldname]["field_type"],
			"mandatory": bool(row.mandatory),
			"description": row.description or available[row.fieldname]["description"],
			"choices": available[row.fieldname]["choices"],
		}
		for row in frappe.get_cached_doc(SETTINGS).get(TABLE_FIELD) or []
		if row.fieldname in available
	]


def order_field_values(fields: list[dict], values) -> dict:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	values = values or {}
	if not isinstance(values, dict):
		frappe.throw(_("Your order details could not be read. Refresh the page and try again."))

	return {
		field["fieldname"]: clean_value(
			field["field_type"], field["label"], field["choices"], values.get(field["fieldname"])
		)
		for field in fields
	}


def missing_order_fields(fields: list[dict], doc) -> list[str]:
	return [
		field["label"] for field in fields if field["mandatory"] and is_blank(doc.get(field["fieldname"]))
	]
