# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from vuna_sourcing.utils import CUSTOMER, SUPPLIER, get_party_spec, validate_entity_type
from vuna_sourcing.vuna_sourcing.doctype.party_onboarding_request.party_onboarding_request import (
	get_document_types_for,
)


class PartyOnboardingTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from vuna_sourcing.vuna_sourcing.doctype.party_onboarding_document_requirement.party_onboarding_document_requirement import (
			PartyOnboardingDocumentRequirement,
		)

		customer_group: DF.Link | None
		default_currency: DF.Link | None
		description: DF.SmallText | None
		disabled: DF.Check
		entity_type: DF.Literal[None]
		is_default: DF.Check
		party_type: DF.Literal["", "Supplier", "Customer"]
		payment_terms: DF.Link | None
		require_registration_number: DF.Check
		require_tax_id: DF.Check
		required_documents: DF.Table[PartyOnboardingDocumentRequirement]
		supplier_group: DF.Link | None
		template_name: DF.Data
		territory: DF.Link | None
	# end: auto-generated types

	def validate(self):
		get_party_spec(self.party_type)
		validate_entity_type(self.party_type, self.entity_type, self.meta.get_label("entity_type"))
		self.clear_other_party_fields()
		self.validate_documents()
		self.validate_single_default()

	def clear_other_party_fields(self):
		if self.party_type == SUPPLIER:
			self.customer_group = None
			self.territory = None
		elif self.party_type == CUSTOMER:
			self.supplier_group = None

	def validate_documents(self):
		usable = set(get_document_types_for(self.party_type))
		seen = set()

		for row in self.required_documents:
			if row.document_type in seen:
				frappe.throw(
					_("Row #{0}: {1} is listed more than once.").format(
						row.idx, frappe.bold(row.document_type)
					),
					title=_("Duplicate Document Type"),
				)
			seen.add(row.document_type)

			if row.document_type not in usable and not frappe.db.get_value(
				"Party Document Type", row.document_type, "disabled"
			):
				frappe.throw(
					_("Row #{0}: {1} does not apply to a {2}. Change its Applies To first.").format(
						row.idx, frappe.bold(row.document_type), _(self.party_type).lower()
					),
					title=_("Document Not Applicable"),
				)

	def validate_single_default(self):
		if not self.is_default:
			return

		existing = frappe.db.get_value(
			"Party Onboarding Template",
			{"is_default": 1, "party_type": self.party_type, "name": ("!=", self.name)},
			"name",
		)
		if existing:
			frappe.db.set_value("Party Onboarding Template", existing, "is_default", 0)
			frappe.msgprint(
				_("{0} is no longer the default {1} onboarding type.").format(
					frappe.bold(existing), _(self.party_type).lower()
				),
				indicator="orange",
				alert=True,
			)

	@frappe.whitelist()
	def get_required_documents(self) -> list[dict]:
		self.check_permission("read")

		usable = set(get_document_types_for(self.party_type))
		return [
			{
				"document_type": row.document_type,
				"is_mandatory": row.is_mandatory,
				"description": row.description,
			}
			for row in self.required_documents
			if row.document_type in usable
		]
