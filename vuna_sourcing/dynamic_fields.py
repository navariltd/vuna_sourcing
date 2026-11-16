# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.utils import cstr, getdate

SHORT_TEXT = "Short Text"
LONG_TEXT = "Long Text"
WHOLE_NUMBER = "Whole Number"
NUMBER = "Number"
DATE = "Date"
YES_NO = "Yes / No"
MULTIPLE_CHOICE = "Multiple Choice"
YES = "Yes"
NO = "No"

FIELD_TYPES = (SHORT_TEXT, LONG_TEXT, WHOLE_NUMBER, NUMBER, DATE, YES_NO, MULTIPLE_CHOICE)
TEXT_LENGTHS = {SHORT_TEXT: 140, LONG_TEXT: 2000}
MIN_CHOICES = 2


def choices_of(field_type: str | None, options: str | None) -> list[str]:
	if field_type == YES_NO:
		return [YES, NO]
	if field_type != MULTIPLE_CHOICE:
		return []

	choices = []
	for line in cstr(options).splitlines():
		line = line.strip()
		if line and line not in choices:
			choices.append(line)
	return choices


def validate_choices(row, label: str) -> None:
	if row.get("field_type") not in FIELD_TYPES:
		frappe.throw(_("Row #{0}: choose a type for {1}.").format(row.idx, frappe.bold(label)))

	if row.get("field_type") != MULTIPLE_CHOICE:
		row.options = None
		return

	choices = choices_of(row.field_type, row.options)
	if len(choices) < MIN_CHOICES:
		frappe.throw(
			_("Row #{0}: give {1} at least {2} choices, one per line.").format(
				row.idx, frappe.bold(label), MIN_CHOICES
			),
			title=_("Choices Needed"),
		)
	row.options = "\n".join(choices)


def number_of(field_type: str, label: str, value) -> int | float:
	if isinstance(value, bool):
		value = None
	try:
		number = float(value)
	except TypeError, ValueError:
		number = math.nan

	if not math.isfinite(number):
		frappe.throw(_("Enter a number for {0}.").format(label))
	if field_type == WHOLE_NUMBER and not number.is_integer():
		frappe.throw(_("Enter a whole number for {0}.").format(label))

	return int(number) if field_type == WHOLE_NUMBER else number


def clean_value(field_type: str, label: str, choices: list[str], value):
	if value is None or (isinstance(value, str) and not value.strip()):
		return None

	if field_type in TEXT_LENGTHS:
		if isinstance(value, bool) or not isinstance(value, str | int | float):
			frappe.throw(_("{0} could not be read. Refresh the page and try again.").format(label))
		return cstr(value).strip()[: TEXT_LENGTHS[field_type]]

	if field_type in (WHOLE_NUMBER, NUMBER):
		return number_of(field_type, label, value)

	if field_type == DATE:
		try:
			return str(getdate(cstr(value)))
		except Exception:
			frappe.throw(_("Choose a valid date for {0}.").format(label))

	if value not in choices:
		frappe.throw(_("Choose one of the options for {0}.").format(label))
	return value


def is_blank(value) -> bool:
	return value is None or cstr(value).strip() == ""
