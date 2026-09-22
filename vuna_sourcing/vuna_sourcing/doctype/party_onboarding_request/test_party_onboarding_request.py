# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import base64

import frappe
from frappe.tests import IntegrationTestCase

# These tests run against whatever company, currency and country the site already has.
# Generating ERPNext's test records here would drag in its accounting fixtures, which
# clash with the live data on a configured site.
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Address",
	"Bank",
	"Bank Account",
	"Company",
	"Contact",
	"Country",
	"Currency",
	"Customer",
	"Customer Group",
	"Party Document Type",
	"Party Onboarding Request",
	"Party Onboarding Template",
	"Payment Terms Template",
	"Supplier",
	"Supplier Group",
	"Territory",
	"User",
]

REQUEST = "Party Onboarding Request"
TEMPLATE_DOCTYPE = "Party Onboarding Template"
DOCUMENT_TYPE = "Party Document Type"

DOC_CERT = "_Test Certificate of Incorporation"
DOC_TAX = "_Test Tax Compliance"
DOC_RETIRED = "_Test Retired Document"
DOC_SUPPLIER_ONLY = "_Test Bank Letter"
DOC_CUSTOMER_ONLY = "_Test Credit Application"

SUPPLIER_TEMPLATE = "_Test Company Supplier"
CUSTOMER_TEMPLATE = "_Test Company Customer"


def create_document_type(name, **kwargs):
	if frappe.db.exists(DOCUMENT_TYPE, name):
		return frappe.get_doc(DOCUMENT_TYPE, name)

	return frappe.get_doc({"doctype": DOCUMENT_TYPE, "document_name": name, **kwargs}).insert()


def create_template(name, party_type, documents, **kwargs):
	if frappe.db.exists(TEMPLATE_DOCTYPE, name):
		return frappe.get_doc(TEMPLATE_DOCTYPE, name)

	return frappe.get_doc(
		{
			"doctype": TEMPLATE_DOCTYPE,
			"template_name": name,
			"party_type": party_type,
			"entity_type": "Company",
			"require_bank_details": 0,
			"required_documents": documents,
			**kwargs,
		}
	).insert()


def leaf(doctype):
	return frappe.get_all(doctype, filters={"is_group": 0}, limit=1, pluck="name")[0]


class TestPartyOnboardingRequest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_document_type(DOC_CERT, description="Certificate issued by the registrar.")
		create_document_type(DOC_TAX, has_expiry=1, expiry_reminder_days=30)
		create_document_type(DOC_RETIRED, disabled=1)
		create_document_type(DOC_SUPPLIER_ONLY, applies_to="Supplier")
		create_document_type(DOC_CUSTOMER_ONLY, applies_to="Customer")

		create_template(
			SUPPLIER_TEMPLATE,
			"Supplier",
			[
				{"document_type": DOC_CERT, "is_mandatory": 1},
				{"document_type": DOC_TAX, "is_mandatory": 0},
				{"document_type": DOC_RETIRED, "is_mandatory": 1},
			],
			require_registration_number=1,
		)
		create_template(
			CUSTOMER_TEMPLATE,
			"Customer",
			[
				{"document_type": DOC_CERT, "is_mandatory": 1},
				{"document_type": DOC_CUSTOMER_ONLY, "is_mandatory": 0},
			],
			customer_group=leaf("Customer Group"),
			territory=leaf("Territory"),
			require_shipping_address=1,
		)

		cls.company = frappe.get_all("Company", limit=1, pluck="name")[0]
		cls.country = frappe.db.get_value("Company", cls.company, "country") or "Kenya"

	def contacts(self, billing=None):
		rows = [
			{
				"first_name": "Jane",
				"last_name": "Wanjiku",
				"designation": "Director",
				"email_id": f"{frappe.generate_hash(length=8)}@example.com",
				"mobile_no": "+254700000000",
				"is_primary_contact": 1,
			}
		]
		if billing:
			rows.append({"is_billing_contact": 1, **billing})
		return rows

	def address(self, **overrides):
		return {
			"address_type": "Billing",
			"address_line1": "1 Test Road",
			"city": "Nairobi",
			"country": self.country,
			"is_primary_address": 1,
			**overrides,
		}

	def make_request(self, party_type="Supplier", **overrides):
		values = {
			"doctype": REQUEST,
			"company": self.company,
			"party_type": party_type,
			"onboarding_template": SUPPLIER_TEMPLATE if party_type == "Supplier" else CUSTOMER_TEMPLATE,
			"party_name": frappe.generate_hash(length=8) + " Traders Ltd",
			"country": self.country,
			"tax_id": "TAX-" + frappe.generate_hash(length=8),
			"registration_number": "REG-" + frappe.generate_hash(length=8),
			"contacts": self.contacts(),
			"addresses": [self.address(is_shipping_address=1 if party_type == "Customer" else 0)],
		}
		values.update(overrides)
		return frappe.get_doc(values).insert()

	def attach(self, request, row_idx=0):
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{frappe.generate_hash(length=8)}.txt",
				"attached_to_doctype": request.doctype,
				"attached_to_name": request.name,
				"is_private": 1,
				"content": base64.b64encode(b"test document").decode(),
				"decode": True,
			}
		).insert(ignore_permissions=True)

		request.required_documents[row_idx].attachment = file.file_url
		return file

	def submitted_request(self, party_type="Supplier", **overrides):
		request = self.make_request(party_type, **overrides)
		self.attach(request)
		request.save()
		request.submit()
		return request

	def make_user(self, roles):
		return (
			frappe.get_doc(
				{
					"doctype": "User",
					"email": f"{frappe.generate_hash(length=10)}@example.com",
					"first_name": "Reviewer",
					"send_welcome_email": 0,
					"roles": [{"role": role} for role in roles],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	# ------------------------------------------------------------------
	# Template driven checklist
	# ------------------------------------------------------------------

	def test_documents_pulled_from_template(self):
		request = self.make_request()
		pulled = [row.document_type for row in request.required_documents]

		self.assertIn(DOC_CERT, pulled)
		self.assertIn(DOC_TAX, pulled)
		self.assertNotIn(DOC_RETIRED, pulled, "a disabled document type should not be requested")
		self.assertEqual(request.required_documents[0].description, "Certificate issued by the registrar.")
		self.assertFalse(request.onboarding_status, "a draft carries no review status")

	def test_changing_template_keeps_relevant_uploads(self):
		other = create_document_type("_Test Partnership Deed")
		partnership = create_template(
			"_Test Partnership Supplier",
			"Supplier",
			[
				{"document_type": DOC_CERT, "is_mandatory": 1},
				{"document_type": other.name, "is_mandatory": 1},
			],
		)
		partnership.db_set("entity_type", "Partnership")

		request = self.make_request()
		file = self.attach(request)
		request.save()

		request.onboarding_template = partnership.name
		request.save()

		rows = {row.document_type: row for row in request.required_documents}
		self.assertEqual(set(rows), {DOC_CERT, other.name})
		self.assertEqual(rows[DOC_CERT].attachment, file.file_url, "an upload still required should survive")
		self.assertIsNone(rows[other.name].attachment)

	# ------------------------------------------------------------------
	# Party type
	# ------------------------------------------------------------------

	def test_party_type_is_taken_from_the_template_when_missing(self):
		request = self.make_request(party_type=None, onboarding_template=CUSTOMER_TEMPLATE)
		self.assertEqual(request.party_type, "Customer")

	def test_template_for_the_other_party_is_refused(self):
		self.assertRaises(
			frappe.ValidationError,
			self.make_request,
			party_type="Supplier",
			onboarding_template=CUSTOMER_TEMPLATE,
		)

	def test_unknown_party_type_is_refused(self):
		template = frappe.new_doc(TEMPLATE_DOCTYPE)
		template.update(
			{"template_name": "_Test Employee Type", "party_type": "Employee", "entity_type": "Company"}
		)
		self.assertRaises(frappe.ValidationError, template.insert)

	def test_template_refuses_a_document_meant_for_the_other_party(self):
		template = frappe.new_doc(TEMPLATE_DOCTYPE)
		template.update(
			{
				"template_name": "_Test Mixed Up Supplier",
				"party_type": "Supplier",
				"entity_type": "Company",
				"required_documents": [{"document_type": DOC_CUSTOMER_ONLY}],
			}
		)
		self.assertRaises(frappe.ValidationError, template.insert)

	def test_narrowing_a_document_type_in_use_is_refused(self):
		"""The customer template asks for the certificate — it cannot become supplier-only."""
		document = frappe.get_doc(DOCUMENT_TYPE, DOC_CERT)
		document.applies_to = "Supplier"
		self.assertRaises(frappe.ValidationError, document.save)

	def test_one_default_template_per_party_type(self):
		supplier_default = create_template("_Test Default Supplier", "Supplier", [], is_default=1)
		customer_default = create_template("_Test Default Customer", "Customer", [], is_default=1)

		self.assertTrue(frappe.db.get_value(TEMPLATE_DOCTYPE, supplier_default.name, "is_default"))
		self.assertTrue(frappe.db.get_value(TEMPLATE_DOCTYPE, customer_default.name, "is_default"))

	def test_template_clears_fields_of_the_other_party(self):
		template = create_template(
			"_Test Tidy Supplier",
			"Supplier",
			[],
			customer_group=leaf("Customer Group"),
			territory=leaf("Territory"),
		)
		self.assertIsNone(template.customer_group)
		self.assertIsNone(template.territory)

	# ------------------------------------------------------------------
	# Entity type mapping
	# ------------------------------------------------------------------

	def test_entity_type_options_come_from_the_party_doctype(self):
		from vuna_sourcing.utils import get_entity_type_options

		for party_type, fieldname in (("Supplier", "supplier_type"), ("Customer", "customer_type")):
			expected = frappe.get_meta(party_type).get_field(fieldname).options.split("\n")
			self.assertEqual(get_entity_type_options(party_type), [o.strip() for o in expected if o.strip()])

	def test_entity_type_keeps_no_static_options(self):
		"""The options must be read off Supplier or Customer, never copied into this app."""
		self.assertFalse(frappe.get_meta(TEMPLATE_DOCTYPE).get_field("entity_type").options)
		self.assertFalse(frappe.get_meta(REQUEST).get_field("entity_type").options)

	def test_template_rejects_an_entity_type_the_party_would_not_accept(self):
		template = frappe.new_doc(TEMPLATE_DOCTYPE)
		template.update(
			{"template_name": "_Test Bogus Type", "party_type": "Customer", "entity_type": "Sole Proprietor"}
		)
		self.assertRaises(frappe.ValidationError, template.insert)

	def test_every_template_type_is_valid_on_its_party(self):
		from vuna_sourcing.utils import get_entity_type_options

		for template in frappe.get_all(TEMPLATE_DOCTYPE, fields=["name", "party_type", "entity_type"]):
			self.assertIn(template.entity_type, get_entity_type_options(template.party_type), template.name)

	def test_template_rejects_duplicate_document_type(self):
		duplicate = frappe.copy_doc(frappe.get_doc(TEMPLATE_DOCTYPE, SUPPLIER_TEMPLATE))
		duplicate.template_name = "_Test Duplicate Rows"
		duplicate.append("required_documents", {"document_type": DOC_CERT})

		self.assertRaises(frappe.ValidationError, duplicate.insert)

	# ------------------------------------------------------------------
	# Contacts and addresses
	# ------------------------------------------------------------------

	def test_a_single_contact_and_address_become_primary(self):
		contact = self.contacts()[0]
		contact["is_primary_contact"] = 0
		address = self.address(is_primary_address=0)

		request = self.make_request(contacts=[contact], addresses=[address])

		self.assertTrue(request.contacts[0].is_primary_contact)
		self.assertTrue(request.addresses[0].is_primary_address)

	def test_two_primary_contacts_are_refused(self):
		contacts = self.contacts() + self.contacts()
		self.assertRaises(frappe.ValidationError, self.make_request, contacts=contacts)

	def test_two_primary_addresses_are_refused(self):
		self.assertRaises(
			frappe.ValidationError,
			self.make_request,
			addresses=[self.address(), self.address(city="Mombasa")],
		)

	def test_submit_needs_a_primary_contact(self):
		request = self.make_request(contacts=[])
		self.attach(request)
		request.save()
		self.assertRaises(frappe.ValidationError, request.submit)

	def test_submit_needs_a_registered_address(self):
		request = self.make_request(addresses=[])
		self.attach(request)
		request.save()
		self.assertRaises(frappe.ValidationError, request.submit)

	def test_a_customer_needs_somewhere_to_deliver(self):
		request = self.make_request("Customer", addresses=[self.address(is_shipping_address=0)])
		self.attach(request)
		request.save()

		self.assertRaises(frappe.ValidationError, request.submit)

	def test_a_supplier_is_not_asked_for_a_delivery_address(self):
		request = self.submitted_request(addresses=[self.address(is_shipping_address=0)])
		self.assertEqual(request.onboarding_status, "Pending Review")

	# ------------------------------------------------------------------
	# Submission
	# ------------------------------------------------------------------

	def test_submit_blocked_without_mandatory_document(self):
		request = self.make_request()
		self.assertRaises(frappe.ValidationError, request.submit)

	def test_submit_sets_pending_review(self):
		request = self.submitted_request()
		self.assertEqual(request.onboarding_status, "Pending Review")
		self.assertIsNone(request.reviewed_by)

	def test_expiry_before_issue_date_rejected(self):
		request = self.make_request()
		request.required_documents[1].issue_date = "2026-06-01"
		request.required_documents[1].expiry_date = "2026-01-01"

		self.assertRaises(frappe.ValidationError, request.save)

	def test_duplicate_tax_id_blocked(self):
		first = self.make_request()
		self.assertRaises(frappe.ValidationError, self.make_request, tax_id=first.tax_id)

	def test_the_same_business_may_be_both_supplier_and_customer(self):
		"""Duplicates are per party type: selling to us and buying from us are different relationships."""
		supplier_request = self.make_request("Supplier")
		customer_request = self.make_request(
			"Customer",
			tax_id=supplier_request.tax_id,
			registration_number=supplier_request.registration_number,
		)
		self.assertEqual(customer_request.tax_id, supplier_request.tax_id)

	def test_duplicate_tax_id_against_existing_supplier_blocked(self):
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": "_Test Existing Supplier " + frappe.generate_hash(length=6),
				"supplier_group": leaf("Supplier Group"),
				"tax_id": "TAX-EXISTING-" + frappe.generate_hash(length=6),
			}
		).insert()

		self.assertRaises(frappe.ValidationError, self.make_request, tax_id=supplier.tax_id)
		self.make_request("Customer", tax_id=supplier.tax_id)

	def test_duplicate_tax_id_against_existing_customer_blocked(self):
		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": "_Test Existing Customer " + frappe.generate_hash(length=6),
				"customer_type": "Company",
				"tax_id": "TAX-EXISTING-" + frappe.generate_hash(length=6),
			}
		).insert()

		self.assertRaises(frappe.ValidationError, self.make_request, "Customer", tax_id=customer.tax_id)

	def test_missing_type_specific_detail_blocks_submission(self):
		request = self.make_request(registration_number=None)
		self.attach(request)
		request.save()

		self.assertRaises(frappe.ValidationError, request.submit)

	def test_party_type_cannot_change_after_submit(self):
		request = self.submitted_request()
		request.party_type = "Customer"
		request.onboarding_template = CUSTOMER_TEMPLATE
		request.flags.ignore_validate_update_after_submit = True

		self.assertRaises(frappe.ValidationError, request.save)

	# ------------------------------------------------------------------
	# What approval creates
	# ------------------------------------------------------------------

	def test_approval_creates_supplier_contacts_and_address(self):
		request = self.submitted_request()
		supplier_name = request.approve(remarks="Checked and in order.")
		request.reload()

		self.assertEqual(request.onboarding_status, "Approved")
		self.assertEqual(request.party, supplier_name)
		self.assertEqual(request.reviewed_by, frappe.session.user)
		self.assertIsNotNone(request.reviewed_on)
		self.assertEqual(request.review_remarks, "Checked and in order.")

		supplier = frappe.get_doc("Supplier", supplier_name)
		self.assertEqual(supplier.supplier_type, "Company")
		self.assertEqual(supplier.tax_id, request.tax_id)
		self.assertEqual(supplier.supplier_primary_contact, request.contacts[0].contact)
		self.assertEqual(supplier.supplier_primary_address, request.addresses[0].address)
		self.assertEqual(
			frappe.db.get_value("Contact", request.contacts[0].contact, "designation"), "Director"
		)

		self.assertTrue(
			frappe.db.count("File", {"attached_to_doctype": "Supplier", "attached_to_name": supplier_name}),
			"supporting documents should be copied onto the supplier record",
		)

	def test_document_copies_are_complete_rows_outside_tests(self):
		"""copy_doc keeps docstatus under tests but clears it on a live site — approve must cope."""
		from unittest.mock import patch

		request = self.submitted_request("Customer")
		with patch.object(frappe, "in_test", False):
			customer = request.approve()

		copies = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Customer", "attached_to_name": customer},
			fields=["docstatus", "owner", "creation"],
		)
		self.assertTrue(copies)
		for row in copies:
			self.assertEqual(row.docstatus, 0)
			self.assertEqual(row.owner, frappe.session.user)
			self.assertIsNotNone(row.creation)

	def test_approval_creates_customer_with_group_territory_and_delivery_address(self):
		delivery = self.address(
			address_type="Shipping", address_line1="9 Depot Lane", is_primary_address=0, is_shipping_address=1
		)
		request = self.submitted_request(
			"Customer",
			addresses=[self.address(is_shipping_address=0), delivery],
		)
		customer_name = request.approve()
		request.reload()

		customer = frappe.get_doc("Customer", customer_name)
		self.assertEqual(request.party, customer_name)
		self.assertEqual(customer.customer_type, "Company")
		self.assertEqual(customer.customer_group, leaf("Customer Group"))
		self.assertEqual(customer.territory, leaf("Territory"))
		self.assertEqual(customer.customer_primary_address, request.addresses[0].address)

		shipping = frappe.get_doc("Address", request.addresses[1].address)
		self.assertEqual(shipping.address_type, "Shipping")
		self.assertTrue(shipping.is_shipping_address)
		self.assertIn(
			customer_name, [link.link_name for link in shipping.links if link.link_doctype == "Customer"]
		)

		self.assertTrue(
			frappe.db.count("File", {"attached_to_doctype": "Customer", "attached_to_name": customer_name}),
			"supporting documents should be copied onto the customer record",
		)

	def test_the_primary_contact_does_billing_unless_someone_else_does(self):
		alone = self.submitted_request()
		alone.approve()
		alone.reload()
		self.assertTrue(frappe.db.get_value("Contact", alone.contacts[0].contact, "is_billing_contact"))

		billing = {"first_name": "Otis", "email_id": f"{frappe.generate_hash(length=8)}@example.com"}
		split = self.submitted_request("Customer", contacts=self.contacts(billing=billing))
		split.approve()
		split.reload()

		primary, accounts = split.contacts
		self.assertFalse(frappe.db.get_value("Contact", primary.contact, "is_billing_contact"))
		self.assertTrue(frappe.db.get_value("Contact", accounts.contact, "is_billing_contact"))
		self.assertFalse(frappe.db.get_value("Contact", accounts.contact, "is_primary_contact"))

	def test_template_defaults_fill_what_the_request_left_blank(self):
		request = self.make_request("Customer")
		self.assertEqual(request.customer_group, leaf("Customer Group"))
		self.assertEqual(request.territory, leaf("Territory"))
		self.assertIsNone(request.supplier_group, "a customer request carries no supplier group")

	def test_approval_links_portal_user(self):
		for party_type in ("Supplier", "Customer"):
			user = self.make_user([])
			request = self.submitted_request(party_type, applicant_user=user)
			party = request.approve()

			self.assertIn(user, [row.user for row in frappe.get_doc(party_type, party).portal_users])
			self.assertIn(party_type, frappe.get_roles(user), "ERPNext grants the role with the portal row")

	# ------------------------------------------------------------------
	# Who may decide an outcome
	# ------------------------------------------------------------------

	def test_applicant_can_submit_but_not_approve(self):
		"""Submitting is not deciding: the outcome is not the submitter's to set."""
		applicant = self.make_user(["Purchase User"])
		request = self.submitted_request()

		with self.set_user(applicant):
			self.assertRaises(frappe.PermissionError, request.approve)
			self.assertRaises(frappe.PermissionError, request.reject, reason="no")
			self.assertRaises(frappe.PermissionError, request.return_for_correction, reason="fix it")

		request.reload()
		self.assertEqual(request.onboarding_status, "Pending Review")
		self.assertIsNone(request.party, "nothing may be created by a non-reviewer")

	def test_submit_is_not_restricted_to_reviewers(self):
		for role in ("Purchase User", "Sales User"):
			with self.set_user(self.make_user([role])):
				self.assertTrue(frappe.has_permission(REQUEST, "submit"), role)

	def test_purchasing_reviews_suppliers_and_sales_reviews_customers(self):
		purchasing = self.make_user(["Purchase Master Manager"])
		sales = self.make_user(["Sales Master Manager"])

		supplier_request = self.submitted_request("Supplier")
		customer_request = self.submitted_request("Customer")

		with self.set_user(sales):
			self.assertRaises(frappe.PermissionError, supplier_request.approve)
		with self.set_user(purchasing):
			self.assertRaises(frappe.PermissionError, customer_request.approve)

		with self.set_user(purchasing):
			supplier_request.approve(remarks="Fine.")
		with self.set_user(sales):
			customer_request.approve(remarks="Fine.")

		for request, reviewer in ((supplier_request, purchasing), (customer_request, sales)):
			request.reload()
			self.assertEqual(request.onboarding_status, "Approved")
			self.assertEqual(request.reviewed_by, reviewer)

	def test_reject_requires_reason(self):
		request = self.submitted_request()
		self.assertRaises(frappe.ValidationError, request.reject, reason="")

	def test_reject_records_reason(self):
		request = self.submitted_request()
		request.reject(reason="Tax certificate is not legible.")
		request.reload()

		self.assertEqual(request.onboarding_status, "Rejected")
		self.assertEqual(request.review_remarks, "Tax certificate is not legible.")
		self.assertIsNone(request.party)

	def test_return_for_correction(self):
		request = self.submitted_request()
		request.return_for_correction(reason="Bank letter is missing.")
		request.reload()

		self.assertEqual(request.onboarding_status, "Returned for Correction")
		self.assertEqual(request.review_remarks, "Bank letter is missing.")

	def test_cannot_review_twice(self):
		request = self.submitted_request()
		request.approve()
		request.reload()

		self.assertRaises(frappe.ValidationError, request.reject, reason="changed my mind")

	def test_cannot_review_a_draft(self):
		request = self.make_request()
		self.assertRaises(frappe.ValidationError, request.approve)

	def test_cancel_blocked_once_party_exists(self):
		request = self.submitted_request()
		request.approve()
		request.reload()

		self.assertRaises(frappe.ValidationError, request.cancel)

	def test_verification_stamps_reviewer(self):
		request = self.submitted_request()
		request.required_documents[0].is_verified = 1
		request.save()

		row = request.required_documents[0]
		self.assertEqual(row.verified_by, frappe.session.user)
		self.assertIsNotNone(row.verified_on)
