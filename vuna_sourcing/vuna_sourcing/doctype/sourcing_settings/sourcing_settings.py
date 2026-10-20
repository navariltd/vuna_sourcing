# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class SourcingSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		accept_customer_applications: DF.Check
		accept_supplier_applications: DF.Check
		allow_any_member_to_open: DF.Check
		allow_customer_sales_orders: DF.Check
		allow_opening_before_bids_close: DF.Check
		allow_opening_below_minimum: DF.Check
		allowed_file_types: DF.Data | None
		contact_email: DF.Data | None
		create_purchase_orders_on_award: DF.Check
		create_address_on_approval: DF.Check
		create_bank_account_on_approval: DF.Check
		create_contact_on_approval: DF.Check
		default_customer_group: DF.Link | None
		default_supplier_group: DF.Link | None
		default_territory: DF.Link | None
		invitation_validity_days: DF.Int
		link_portal_user_on_approval: DF.Check
		max_file_size_mb: DF.Float
		notify_applicant: DF.Check
		notify_reviewers: DF.Check
		registration_mode: DF.Literal["Invitation Only", "Open to Public"]
		reviewer_role: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if flt(self.max_file_size_mb) < 0:
			frappe.throw(_("Maximum File Size (MB) cannot be negative."))

		if cint(self.invitation_validity_days) < 0:
			frappe.throw(_("Invitation Valid For (Days) cannot be negative."))

		self.normalise_allowed_file_types()

		if not (self.accept_supplier_applications or self.accept_customer_applications):
			frappe.msgprint(
				_(
					"Neither supplier nor customer applications are accepted, so the portal will not offer an application form."
				),
				indicator="orange",
				alert=True,
			)

	def normalise_allowed_file_types(self):
		if not self.allowed_file_types:
			return

		extensions = [
			part.strip().lower().lstrip(".")
			for part in self.allowed_file_types.replace("|", ",").split(",")
			if part.strip()
		]
		self.allowed_file_types = ", ".join(dict.fromkeys(extensions))

	def get_upload_rules(self, document_type: str | None = None) -> dict:
		allowed = self.allowed_file_types
		max_size = self.max_file_size_mb

		if document_type:
			override = frappe.db.get_value(
				"Party Document Type",
				document_type,
				["allowed_file_types", "max_file_size_mb"],
				as_dict=True,
			)
			if override:
				allowed = override.allowed_file_types or allowed
				max_size = override.max_file_size_mb or max_size

		return {
			"allowed_file_types": [ext.strip() for ext in (allowed or "").split(",") if ext.strip()],
			"max_file_size_mb": max_size,
		}

	@frappe.whitelist()
	def get_signup_page(self) -> dict:
		from frappe.utils import get_url

		from vuna_sourcing.api.signup import registration_is_open
		from vuna_sourcing.utils import get_open_party_types

		return {
			"url": get_url("/vuna-sourcing/signup"),
			"is_open": registration_is_open(),
			"registration_mode": self.registration_mode,
			"party_types": get_open_party_types(),
		}
