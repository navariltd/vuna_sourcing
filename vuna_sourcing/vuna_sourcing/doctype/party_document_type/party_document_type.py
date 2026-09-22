# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class PartyDocumentType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allowed_file_types: DF.Data | None
		applies_to: DF.Literal["Supplier and Customer", "Supplier", "Customer"]
		description: DF.SmallText | None
		disabled: DF.Check
		document_name: DF.Data
		expiry_reminder_days: DF.Int
		has_expiry: DF.Check
		max_file_size_mb: DF.Float
	# end: auto-generated types

	def validate(self):
		self.normalise_allowed_file_types()
		self.validate_templates_still_apply()

		if cint(self.expiry_reminder_days) < 0:
			frappe.throw(_("Expiry Reminder (Days) cannot be negative."))

		if flt(self.max_file_size_mb) < 0:
			frappe.throw(_("Maximum File Size (MB) cannot be negative."))

	def normalise_allowed_file_types(self):
		if not self.allowed_file_types:
			return

		extensions = [
			part.strip().lower().lstrip(".")
			for part in self.allowed_file_types.replace("|", ",").split(",")
			if part.strip()
		]
		self.allowed_file_types = ", ".join(dict.fromkeys(extensions))

	def validate_templates_still_apply(self):
		if self.is_new() or self.applies_to == "Supplier and Customer":
			return

		requirement = frappe.qb.DocType("Party Onboarding Document Requirement")
		template = frappe.qb.DocType("Party Onboarding Template")
		stranded = (
			frappe.qb.from_(requirement)
			.join(template)
			.on(template.name == requirement.parent)
			.select(template.name)
			.distinct()
			.where(requirement.parenttype == "Party Onboarding Template")
			.where(requirement.document_type == self.name)
			.where(template.party_type != self.applies_to)
			.run(pluck=True)
		)
		if stranded:
			frappe.throw(
				_("{0} is still asked for by these onboarding types, which are not for a {1}: {2}").format(
					frappe.bold(self.name),
					_(self.applies_to).lower(),
					", ".join(frappe.bold(name) for name in stranded),
				),
				title=_("Still In Use"),
			)
