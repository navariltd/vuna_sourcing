# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import IfNull
from frappe.utils import get_link_to_form, getdate, now_datetime, today

from vuna_sourcing.utils import CUSTOMER, SUPPLIER, get_party_spec, validate_entity_type

PENDING_REVIEW = "Pending Review"
APPROVED = "Approved"
REJECTED = "Rejected"
RETURNED = "Returned for Correction"

DOCTYPE = "Party Onboarding Request"
TEMPLATE_DOCTYPE = "Party Onboarding Template"
DOCUMENT_TYPE_DOCTYPE = "Party Document Type"


class PartyOnboardingRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from vuna_sourcing.vuna_sourcing.doctype.party_onboarding_address.party_onboarding_address import (
			PartyOnboardingAddress,
		)
		from vuna_sourcing.vuna_sourcing.doctype.party_onboarding_contact.party_onboarding_contact import (
			PartyOnboardingContact,
		)
		from vuna_sourcing.vuna_sourcing.doctype.party_onboarding_request_document.party_onboarding_request_document import (
			PartyOnboardingRequestDocument,
		)

		account_holder_name: DF.Data | None
		addresses: DF.Table[PartyOnboardingAddress]
		amended_from: DF.Link | None
		applicant_user: DF.Link | None
		bank: DF.Link | None
		bank_account: DF.Link | None
		bank_account_no: DF.Data | None
		branch_code: DF.Data | None
		company: DF.Link
		company_logo: DF.AttachImage | None
		contacts: DF.Table[PartyOnboardingContact]
		country: DF.Link | None
		customer_group: DF.Link | None
		default_currency: DF.Link | None
		entity_type: DF.Literal[None]
		iban: DF.Data | None
		naming_series: DF.Literal["POR-.YYYY.-", "SOR-.YYYY.-"]
		onboarding_status: DF.Literal["", "Pending Review", "Approved", "Rejected", "Returned for Correction"]
		onboarding_template: DF.Link
		party: DF.DynamicLink | None
		party_name: DF.Data
		party_type: DF.Literal["", "Supplier", "Customer"]
		payment_terms: DF.Link | None
		registration_number: DF.Data | None
		required_documents: DF.Table[PartyOnboardingRequestDocument]
		review_remarks: DF.SmallText | None
		reviewed_by: DF.Link | None
		reviewed_on: DF.Datetime | None
		supplier_group: DF.Link | None
		swift_number: DF.Data | None
		tax_id: DF.Data | None
		territory: DF.Link | None
		website: DF.Data | None
	# end: auto-generated types

	@property
	def spec(self):
		return get_party_spec(self.party_type)

	@property
	def template(self):
		if not self.onboarding_template:
			return None
		return frappe.get_cached_doc(TEMPLATE_DOCTYPE, self.onboarding_template)

	def onload(self):
		self.set_onload("settings", get_settings().as_dict())

	def validate(self):
		self.validate_party_type()
		self.sync_documents_from_template()
		self.apply_template_defaults()
		self.normalise_contacts_and_addresses()
		self.validate_required_details()
		self.validate_duplicate_registration()
		self.validate_document_dates()
		self.stamp_verifications()

		if self.docstatus == 0 and self.onboarding_status != RETURNED:
			self.onboarding_status = None

	def before_submit(self):
		self.validate_mandatory_documents()
		self.onboarding_status = PENDING_REVIEW
		self.reviewed_by = None
		self.reviewed_on = None
		self.review_remarks = None

	def before_update_after_submit(self):
		self.validate_locked_after_submit()
		self.normalise_contacts_and_addresses()
		self.validate_document_dates()
		self.stamp_verifications()

	def on_submit(self):
		self.notify_applicant(
			_("Onboarding request received"),
			_("We have received your onboarding request {0} and it is now with our team for review.").format(
				self.name
			),
		)

	def before_cancel(self):
		if self.party:
			frappe.throw(
				_("{0} was already created from this request. Cancel is not allowed.").format(
					get_link_to_form(self.party_type, self.party)
				),
				title=_("Cannot Cancel"),
			)
		if self.onboarding_status not in (REJECTED, RETURNED):
			self.onboarding_status = RETURNED

	def validate_party_type(self):
		template = self.template

		if not self.party_type and template:
			self.party_type = template.party_type

		if not self.party_type:
			return

		get_party_spec(self.party_type)

		if template and template.party_type != self.party_type:
			frappe.throw(
				_("{0} is for onboarding a {1}, but this request is applying as a {2}.").format(
					frappe.bold(template.name), _(template.party_type), _(self.party_type)
				),
				title=_("Wrong Onboarding Type"),
			)

		validate_entity_type(self.party_type, self.entity_type, self.meta.get_label("entity_type"))

	def validate_locked_after_submit(self):
		previous = self.get_doc_before_save()
		if not previous:
			return

		for fieldname in ("party_type", "onboarding_template"):
			if previous.get(fieldname) != self.get(fieldname):
				frappe.throw(
					_(
						"{0} cannot change once a request has been submitted. Start a new application instead."
					).format(frappe.bold(self.meta.get_label(fieldname))),
					title=_("Not Allowed"),
				)

	def sync_documents_from_template(self):
		if self.docstatus != 0 or not self.onboarding_template:
			return

		template = self.template
		if template.disabled:
			frappe.throw(
				_("Onboarding type {0} is disabled.").format(frappe.bold(template.name)),
				title=_("Template Disabled"),
			)

		usable = set(get_document_types_for(self.party_type))
		existing = {row.document_type: row for row in self.required_documents}

		rows = []
		for requirement in template.required_documents:
			if requirement.document_type not in usable:
				continue

			row = existing.get(requirement.document_type) or frappe._dict(
				{"document_type": requirement.document_type}
			)
			rows.append(
				{
					"document_type": requirement.document_type,
					"is_mandatory": requirement.is_mandatory,
					"description": requirement.description,
					"attachment": row.get("attachment"),
					"document_number": row.get("document_number"),
					"issue_date": row.get("issue_date"),
					"expiry_date": row.get("expiry_date"),
					"is_verified": row.get("is_verified"),
					"verified_by": row.get("verified_by"),
					"verified_on": row.get("verified_on"),
					"remarks": row.get("remarks"),
				}
			)

		self.required_documents = []
		for row in rows:
			self.append("required_documents", row)

	def apply_template_defaults(self):
		if not self.party_type:
			return

		template = self.template
		settings = get_settings()

		def fill(fieldname, *candidates):
			if not self.get(fieldname):
				self.set(fieldname, next((value for value in candidates if value), None))

		if template:
			self.entity_type = template.entity_type
			fill("default_currency", template.default_currency)
			fill("payment_terms", template.payment_terms)

		if self.party_type == SUPPLIER:
			fill("supplier_group", template and template.supplier_group, settings.default_supplier_group)
			self.customer_group = None
			self.territory = None
		else:
			fill("customer_group", template and template.customer_group, settings.default_customer_group)
			fill("territory", template and template.territory, settings.default_territory)
			self.supplier_group = None

	def normalise_contacts_and_addresses(self):
		for row in self.contacts:
			for fieldname in ("first_name", "last_name", "email_id", "mobile_no", "designation"):
				row.set(fieldname, (row.get(fieldname) or "").strip() or None)
			if row.email_id:
				row.email_id = row.email_id.lower()

		for row in self.addresses:
			for fieldname in ("address_line1", "address_line2", "city", "state", "pincode"):
				row.set(fieldname, (row.get(fieldname) or "").strip() or None)
			row.address_type = row.address_type or "Billing"

		if len(self.contacts) == 1:
			self.contacts[0].is_primary_contact = 1
		if len(self.addresses) == 1:
			self.addresses[0].is_primary_address = 1

		for table, flag, label in (
			("contacts", "is_primary_contact", _("contact")),
			("addresses", "is_primary_address", _("address")),
		):
			primaries = [row for row in self.get(table) if row.get(flag)]
			if len(primaries) > 1:
				frappe.throw(
					_("Only one {0} can be primary. Rows {1} are all marked primary.").format(
						label, ", ".join(str(row.idx) for row in primaries)
					),
					title=_("More Than One Primary"),
				)

	def get_primary_contact(self):
		return next((row for row in self.contacts if row.is_primary_contact), None)

	def get_billing_contact(self):
		return (
			next((row for row in self.contacts if row.is_billing_contact), None) or self.get_primary_contact()
		)

	def get_primary_address(self):
		return next((row for row in self.addresses if row.is_primary_address), None)

	def get_outstanding_details(self) -> tuple[list[str], list[str]]:
		always = []
		template = self.template

		if not self.party_type:
			always.append(_("Whether you are applying as a supplier or a customer"))
		if not self.onboarding_template:
			always.append(_("Onboarding type"))
		if not self.party_name:
			always.append(_("Name"))

		primary = self.get_primary_contact()
		if not primary:
			always.append(_("A primary contact"))
		else:
			for fieldname, label in (
				("first_name", _("Primary contact first name")),
				("last_name", _("Primary contact last name")),
				("email_id", _("Primary contact email address")),
				("mobile_no", _("Primary contact mobile number")),
			):
				if not primary.get(fieldname):
					always.append(label)

		for row in self.contacts:
			if row is primary:
				continue
			who = _("Billing contact") if row.is_billing_contact else _("Contact #{0}").format(row.idx)
			if not row.first_name:
				always.append(_("{0} first name").format(who))
			if not row.email_id:
				always.append(_("{0} email address").format(who))

		primary_address = self.get_primary_address()
		if not primary_address:
			always.append(_("A registered address"))

		for row in self.addresses:
			where = (
				_("Registered address")
				if row is primary_address
				else _("{0} address #{1}").format(_(row.address_type), row.idx)
			)
			if not row.address_line1:
				always.append(_("{0}: address line 1").format(where))
			if not row.city:
				always.append(_("{0}: city / town").format(where))
			if not row.country:
				always.append(_("{0}: country").format(where))

		by_type = []
		if template:
			if template.require_tax_id and not self.tax_id:
				by_type.append(_("Tax registration number"))
			if template.require_registration_number and not self.registration_number:
				by_type.append(_("Company registration number"))
			if template.require_bank_details and not (self.bank and self.bank_account_no):
				by_type.append(_("Bank details (bank and account number)"))
			if (
				self.party_type == CUSTOMER
				and template.require_shipping_address
				and not any(row.is_shipping_address for row in self.addresses)
			):
				by_type.append(_("A delivery address"))

		return always, by_type

	def validate_required_details(self):
		always, by_type = self.get_outstanding_details()
		if not (always or by_type):
			return

		parts = []
		if always:
			parts.append(_("Still needed:") + "<br><ul><li>" + "</li><li>".join(always) + "</li></ul>")
		if by_type:
			parts.append(
				_("Required for {0}:").format(frappe.bold(self.onboarding_template))
				+ "<br><ul><li>"
				+ "</li><li>".join(by_type)
				+ "</li></ul>"
			)

		message = "".join(parts)

		if self.docstatus == 0:
			if not self.flags.silent_outstanding:
				frappe.msgprint(message, indicator="orange", title=_("Still Outstanding"))
		else:
			frappe.throw(message, title=_("Missing Details"))

	def validate_mandatory_documents(self):
		missing = [
			row.document_type for row in self.required_documents if row.is_mandatory and not row.attachment
		]
		if missing:
			frappe.throw(
				_("These supporting documents are required before this request can be submitted:")
				+ "<br><ul><li>"
				+ "</li><li>".join(frappe.bold(name) for name in missing)
				+ "</li></ul>",
				title=_("Supporting Documents Missing"),
			)

	def validate_document_dates(self):
		for row in self.required_documents:
			if row.issue_date and row.expiry_date and getdate(row.expiry_date) < getdate(row.issue_date):
				frappe.throw(
					_("Row #{0}: Expiry Date cannot be before Issue Date.").format(row.idx),
					title=_("Invalid Dates"),
				)

			if self.docstatus == 0 and row.expiry_date and getdate(row.expiry_date) < getdate(today()):
				frappe.msgprint(
					_("Row #{0}: {1} expired on {2}.").format(
						row.idx,
						frappe.bold(row.document_type),
						frappe.format(row.expiry_date, "Date"),
					),
					indicator="orange",
					alert=True,
				)

	def stamp_verifications(self):
		for row in self.required_documents:
			if row.is_verified and not row.verified_by:
				row.verified_by = frappe.session.user
				row.verified_on = now_datetime()
			elif not row.is_verified:
				row.verified_by = None
				row.verified_on = None

	def validate_duplicate_registration(self):
		if not self.party_type:
			return

		spec = self.spec
		for fieldname, label in (
			("tax_id", _("Tax Registration Number")),
			("registration_number", _("Company Registration Number")),
		):
			value = (self.get(fieldname) or "").strip()
			if not value:
				continue

			self.set(fieldname, value)

			if fieldname == "tax_id":
				existing = frappe.db.get_value(spec.doctype, {"tax_id": value}, "name")
				if existing and existing != self.party:
					frappe.throw(
						_("{0} {1} already belongs to {2} {3}.").format(
							label,
							frappe.bold(value),
							_(spec.doctype).lower(),
							get_link_to_form(spec.doctype, existing),
						),
						title=_("Already Registered"),
					)

			request = frappe.qb.DocType(DOCTYPE)
			duplicate = (
				frappe.qb.from_(request)
				.select(request.name)
				.where(request[fieldname] == value)
				.where(request.party_type == self.party_type)
				.where(request.name != self.name)
				.where(request.docstatus < 2)
				.where(IfNull(request.onboarding_status, "").notin([REJECTED, RETURNED]))
				.limit(1)
				.run(pluck=True)
			)
			if duplicate:
				frappe.throw(
					_("{0} {1} is already on {2} onboarding request {3}.").format(
						label,
						frappe.bold(value),
						_(self.party_type).lower(),
						get_link_to_form(DOCTYPE, duplicate[0]),
					),
					title=_("Duplicate Request"),
				)

	@frappe.whitelist()
	def approve(self, remarks: str | None = None):
		self.check_reviewer()
		self.validate_review_state()
		self.validate_mandatory_documents()

		settings = get_settings()

		party = self.create_party()
		if settings.create_contact_on_approval:
			self.create_contacts(party)
		if settings.create_address_on_approval:
			self.create_addresses(party)
		bank_account = self.create_bank_account(party) if settings.create_bank_account_on_approval else None

		self.attach_documents_to_party(party)

		if settings.link_portal_user_on_approval:
			self.link_portal_user(party)

		self.db_set(
			{
				"party": party.name,
				"bank_account": bank_account.name if bank_account else None,
				"onboarding_status": APPROVED,
				"reviewed_by": frappe.session.user,
				"reviewed_on": now_datetime(),
				"review_remarks": remarks,
			}
		)

		self.add_review_comment(_("Approved"), remarks)
		self.notify_applicant(
			_("Onboarding approved"),
			_("Your onboarding request {0} has been approved. You are now set up as a {1}.").format(
				self.name, _(self.party_type).lower()
			),
		)

		frappe.msgprint(
			_("{0} {1} created.").format(_(self.party_type), get_link_to_form(self.party_type, party.name)),
			indicator="green",
			alert=True,
		)
		return party.name

	@frappe.whitelist()
	def reject(self, reason: str):
		self.check_reviewer()
		self.validate_review_state()

		if not reason:
			frappe.throw(_("A reason is required when rejecting a request."))

		self.db_set(
			{
				"onboarding_status": REJECTED,
				"reviewed_by": frappe.session.user,
				"reviewed_on": now_datetime(),
				"review_remarks": reason,
			}
		)

		self.add_review_comment(_("Rejected"), reason)
		self.notify_applicant(
			_("Onboarding request rejected"),
			_("Your onboarding request {0} was not approved.<br><br>Reason: {1}").format(self.name, reason),
		)

	@frappe.whitelist()
	def return_for_correction(self, reason: str):
		self.check_reviewer()
		self.validate_review_state()

		if not reason:
			frappe.throw(_("A reason is required when returning a request for correction."))

		self.db_set(
			{
				"onboarding_status": RETURNED,
				"reviewed_by": frappe.session.user,
				"reviewed_on": now_datetime(),
				"review_remarks": reason,
			}
		)

		self.add_review_comment(_("Returned for correction"), reason)
		self.notify_applicant(
			_("Onboarding request returned"),
			_(
				"Your onboarding request {0} needs correction before we can proceed."
				"<br><br>What needs attention: {1}"
			).format(self.name, reason),
		)

	def check_reviewer(self):
		frappe.only_for(self.spec.reviewer_roles, message=True)
		self.check_permission("submit")

	def validate_review_state(self):
		if self.docstatus != 1:
			frappe.throw(_("Only a submitted request can be reviewed."))

		if self.onboarding_status != PENDING_REVIEW:
			frappe.throw(
				_("This request is {0} and is no longer awaiting review.").format(
					frappe.bold(self.onboarding_status)
				)
			)

	def add_review_comment(self, action: str, remarks: str | None):
		text = f"<b>{action}</b>"
		if remarks:
			text += f"<br>{frappe.utils.escape_html(remarks)}"
		self.add_comment("Comment", text)

	def create_party(self):
		spec = self.spec
		validate_entity_type(self.party_type, self.entity_type, self.meta.get_label("entity_type"))

		values = {
			spec.name_field: self.party_name,
			spec.entity_field: self.entity_type,
			spec.group_field: self.get(spec.group_field),
			"image": self.company_logo,
			"tax_id": self.tax_id,
			"website": self.website,
			"default_currency": self.default_currency,
			"payment_terms": self.payment_terms,
		}
		if self.party_type == SUPPLIER:
			values["country"] = self.country or (self.get_primary_address() or {}).get("country")
		else:
			values["territory"] = self.territory

		party = frappe.new_doc(spec.doctype)
		party.update(values)
		party.insert(ignore_permissions=True)
		return party

	def create_contacts(self, party):
		spec = self.spec
		billing = self.get_billing_contact()
		primary = self.get_primary_contact()

		for row in self.contacts:
			if not (row.first_name and row.email_id):
				continue

			contact = frappe.get_doc(
				{
					"doctype": "Contact",
					"first_name": row.first_name,
					"last_name": row.last_name,
					"designation": row.designation,
					"company_name": self.party_name,
					"is_primary_contact": 1 if row is primary else 0,
					"is_billing_contact": 1 if row is billing else 0,
					"links": [{"link_doctype": spec.doctype, "link_name": party.name}],
				}
			)
			contact.add_email(row.email_id, is_primary=True)
			if row.mobile_no:
				contact.add_phone(row.mobile_no, is_primary_mobile_no=True)
			contact.insert(ignore_permissions=True)
			row.db_set("contact", contact.name)

			if row is primary:
				party.db_set(
					{
						spec.primary_contact_field: contact.name,
						"mobile_no": row.mobile_no,
						"email_id": row.email_id,
					}
				)

	def create_addresses(self, party):
		spec = self.spec

		for row in self.addresses:
			if not (row.address_line1 and row.city and row.country):
				continue

			address = frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": self.party_name,
					"address_type": row.address_type or "Billing",
					"address_line1": row.address_line1,
					"address_line2": row.address_line2,
					"city": row.city,
					"state": row.state,
					"pincode": row.pincode,
					"country": row.country,
					"is_primary_address": row.is_primary_address,
					"is_shipping_address": row.is_shipping_address,
					"links": [{"link_doctype": spec.doctype, "link_name": party.name}],
				}
			)
			address.insert(ignore_permissions=True)
			row.db_set("address", address.name)

			if row.is_primary_address:
				party.db_set(spec.primary_address_field, address.name)

	def create_bank_account(self, party):
		if not (self.bank and self.bank_account_no):
			return None

		bank_account = frappe.new_doc("Bank Account")
		bank_account.update(
			{
				"account_name": self.account_holder_name or self.party_name,
				"bank": self.bank,
				"bank_account_no": self.bank_account_no,
				"iban": self.iban,
				"branch_code": self.branch_code,
				"party_type": self.party_type,
				"party": party.name,
				"is_default": 1,
			}
		)
		bank_account.insert(ignore_permissions=True)
		party.db_set("default_bank_account", bank_account.name)
		return bank_account

	def attach_documents_to_party(self, party):
		for row in self.required_documents:
			if not row.attachment:
				continue

			file_name = frappe.db.get_value(
				"File",
				{"file_url": row.attachment, "attached_to_name": self.name},
				"name",
			)
			if not file_name:
				continue

			file_doc = frappe.get_doc("File", file_name)
			party_copy = frappe.copy_doc(file_doc)
			party_copy.update(
				{
					"attached_to_doctype": party.doctype,
					"attached_to_name": party.name,
					"attached_to_field": None,
					"is_private": file_doc.is_private,
					"folder": file_doc.folder,
				}
			)
			party_copy.docstatus = 0
			party_copy.set_new_name()
			party_copy.set_user_and_timestamp()
			party_copy.db_insert()
			party_copy.create_attachment_record()

	def link_portal_user(self, party):
		if not self.applicant_user:
			return

		if any(row.user == self.applicant_user for row in party.portal_users):
			return

		party.reload()
		party.append("portal_users", {"user": self.applicant_user})
		party.save(ignore_permissions=True)

	def notify_applicant(self, subject: str, message: str):
		settings = get_settings()
		if not settings.notify_applicant:
			return

		primary = self.get_primary_contact()
		recipient = primary.email_id if primary else None
		if not recipient and self.applicant_user:
			recipient = frappe.db.get_value("User", self.applicant_user, "email")
		if not recipient:
			return

		try:
			frappe.sendmail(
				recipients=[recipient],
				subject=subject,
				message=message,
				reference_doctype=self.doctype,
				reference_name=self.name,
			)
		except Exception:
			self.log_error("Party onboarding notification failed")


def get_settings():
	return frappe.get_cached_doc("Sourcing Settings")


def drafts_hidden_condition(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	return f"(`tab{DOCTYPE}`.`docstatus` != 0 or `tab{DOCTYPE}`.`owner` = {frappe.db.escape(user)})"


def is_not_others_draft(doc, ptype: str | None = None, user: str | None = None, **kwargs) -> bool:
	if doc.is_new() or doc.docstatus != 0:
		return True
	return doc.owner == (user or frappe.session.user)


def get_document_types_for(party_type: str | None) -> list[str]:
	applies_to = ["Supplier and Customer"]
	if party_type:
		applies_to.append(party_type)

	return frappe.get_all(
		DOCUMENT_TYPE_DOCTYPE,
		filters={"disabled": 0, "applies_to": ("in", applies_to)},
		pluck="name",
	)


@frappe.whitelist()
def get_pending_review_count(party_type: str | None = None) -> int:
	filters = {"docstatus": 1, "onboarding_status": PENDING_REVIEW}
	if party_type:
		filters["party_type"] = party_type
	return frappe.db.count(DOCTYPE, filters)
