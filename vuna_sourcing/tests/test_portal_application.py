# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import base64
from contextlib import contextmanager

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from vuna_sourcing.api.onboarding import (
	attach_uploaded_file,
	download_application,
	get_application,
	get_application_progress,
	get_link_options,
	get_my_applications,
	get_onboarding_types,
	get_own_application,
	get_tax_id_formats,
	resubmit_application,
	save_application,
	save_attachment,
	submit_application,
)
from vuna_sourcing.api.portal import get_linked_parties, get_session
from vuna_sourcing.tests import make_test_user

REQUEST = "Party Onboarding Request"

DOC_CERT = "_Portal Certificate of Incorporation"
DOC_OPTIONAL = "_Portal Company Profile"
DOC_RETIRED = "_Portal Retired Document"
DOC_CUSTOMER_ONLY = "_Portal Credit Application"

SUPPLIER_TEMPLATE = "_Portal Company"
CUSTOMER_TEMPLATE = "_Portal Company Customer"
TEMPLATE_FOR = {"Supplier": SUPPLIER_TEMPLATE, "Customer": CUSTOMER_TEMPLATE}


def blank_pdf() -> bytes:
	"""A real one-page PDF — File validates PDF content on save."""
	from io import BytesIO

	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=72, height=72)
	out = BytesIO()
	writer.write(out)
	return out.getvalue()


def leaf(doctype):
	return frappe.get_all(doctype, filters={"is_group": 0}, limit=1, pluck="name")[0]


class TestPortalApplication(IntegrationTestCase):
	"""The applicant's own journey, run as the applicant — as a supplier and as a customer."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		for name, kwargs in (
			(DOC_CERT, {"description": "Certificate from the registrar."}),
			(DOC_OPTIONAL, {}),
			(DOC_RETIRED, {"disabled": 1}),
			(DOC_CUSTOMER_ONLY, {"applies_to": "Customer"}),
		):
			if not frappe.db.exists("Party Document Type", name):
				frappe.get_doc({"doctype": "Party Document Type", "document_name": name, **kwargs}).insert()

		for name, party_type, extra, documents in (
			(
				SUPPLIER_TEMPLATE,
				"Supplier",
				{},
				[
					{"document_type": DOC_CERT, "is_mandatory": 1},
					{"document_type": DOC_OPTIONAL, "is_mandatory": 0},
					{"document_type": DOC_RETIRED, "is_mandatory": 1},
				],
			),
			(
				CUSTOMER_TEMPLATE,
				"Customer",
				{
					"customer_group": leaf("Customer Group"),
					"territory": leaf("Territory"),
				},
				[
					{"document_type": DOC_CERT, "is_mandatory": 1},
					{"document_type": DOC_CUSTOMER_ONLY, "is_mandatory": 0},
				],
			),
		):
			if not frappe.db.exists("Party Onboarding Template", name):
				frappe.get_doc(
					{
						"doctype": "Party Onboarding Template",
						"template_name": name,
						"party_type": party_type,
						"entity_type": "Company",
						"require_registration_number": 0,
						"required_documents": documents,
						**extra,
					}
				).insert()

		frappe.db.commit()

	def setUp(self):
		super().setUp()
		self.accept("Supplier", True)
		self.accept("Customer", True)

	def accept(self, party_type, on):
		frappe.db.set_single_value(
			"Sourcing Settings", f"accept_{party_type.lower()}_applications", 1 if on else 0
		)
		frappe.clear_document_cache("Sourcing Settings", "Sourcing Settings")

	@contextmanager
	def closed(self, party_type):
		self.accept(party_type, False)
		try:
			yield
		finally:
			self.accept(party_type, True)

	def make_applicant(self, roles=()):
		"""A prospective supplier or customer: a plain signup with no roles, unless told otherwise."""
		return make_test_user(roles, first_name="Amina", last_name="Otieno", user_type="Website User").name

	def contact(self, **overrides):
		return {
			"first_name": "Amina",
			"last_name": "Otieno",
			"email_id": "amina@example.com",
			"mobile_no": "+254711000000",
			"is_primary_contact": 1,
			**overrides,
		}

	def address(self, **overrides):
		return {
			"address_type": "Billing",
			"address_line1": "1 Kenyatta Avenue",
			"city": "Nairobi",
			"country": frappe.get_all("Country", limit=1, pluck="name")[0],
			"is_primary_address": 1,
			**overrides,
		}

	def base_values(self, party_type="Supplier"):
		return {
			"party_type": party_type,
			"onboarding_template": TEMPLATE_FOR[party_type],
			"party_name": "Portal Traders " + frappe.generate_hash(length=6),
			"tax_id": "PTAX-" + frappe.generate_hash(length=8),
			"contacts": [self.contact()],
			"addresses": [self.address(), *([self.delivery()] if party_type == "Customer" else [])],
		}

	def delivery(self, **overrides):
		return self.address(
			address_type="Shipping",
			address_line1="9 Depot Lane",
			is_primary_address=0,
			is_shipping_address=1,
			**overrides,
		)

	def upload(self, docname, filename=None, content=None, document_type=DOC_CERT, purpose=None):
		"""The way the portal attaches: Frappe's upload_file stores the upload, then calls our method."""
		form_dict = frappe.local.form_dict
		frappe.local.form_dict = frappe._dict(
			application=docname, document_type=document_type, purpose=purpose
		)
		frappe.local.uploaded_file = content if content is not None else blank_pdf()
		frappe.local.uploaded_filename = filename or f"{frappe.generate_hash(length=8)}.pdf"
		try:
			response = attach_uploaded_file()
		finally:
			frappe.local.uploaded_file = frappe.local.uploaded_filename = None
			frappe.local.form_dict = form_dict
		return frappe.get_doc(
			"File", {"file_url": response.data["file_url"], "attached_to_name": docname}
		).as_dict()

	def require_expiry(self, document_type=DOC_CERT, template=SUPPLIER_TEMPLATE):
		row = frappe.db.get_value(
			"Party Onboarding Document Requirement", {"parent": template, "document_type": document_type}
		)
		frappe.db.set_value("Party Onboarding Document Requirement", row, "has_expiry", 1)
		frappe.clear_document_cache("Party Onboarding Template", template)

		def restore():
			frappe.db.set_value("Party Onboarding Document Requirement", row, "has_expiry", 0)
			frappe.clear_document_cache("Party Onboarding Template", template)

		self.addCleanup(restore)

	def certificate(self, saved, **dates):
		return [{"document_type": DOC_CERT, "attachment": saved["documents"][0]["attachment"], **dates}]

	def complete(self, applicant, party_type="Supplier", extra=None):
		"""A draft with everything submit needs, saved as the applicant."""
		values = {**self.base_values(party_type), **(extra or {})}
		with self.set_user(applicant):
			saved = save_application(values)
			file = self.upload(saved["name"])
			return save_application(
				{**values, "documents": [{"document_type": DOC_CERT, "attachment": file["file_url"]}]},
				saved["name"],
			)

	def complete_and_submit(self, applicant, party_type="Supplier", extra=None):
		saved = self.complete(applicant, party_type, extra)
		with self.set_user(applicant):
			return submit_application(saved["name"])

	def test_drafts_stay_off_the_desk_until_submitted(self):
		applicant = self.make_applicant()
		draft = self.complete(applicant)["name"]
		reviewer = make_test_user(["Purchase Master Manager"], first_name="Buyer").name

		with self.set_user(reviewer):
			self.assertNotIn(draft, frappe.get_list(REQUEST, pluck="name"))
			self.assertFalse(frappe.has_permission(REQUEST, doc=draft))

		with self.set_user(applicant):
			submit_application(draft)

		with self.set_user(reviewer):
			self.assertIn(draft, frappe.get_list(REQUEST, pluck="name"))
			self.assertTrue(frappe.has_permission(REQUEST, doc=draft))

	def test_a_draft_started_on_the_desk_stays_visible_to_whoever_started_it(self):
		buyer = make_test_user(["Purchase Master Manager"], first_name="Buyer").name
		other_buyer = make_test_user(["Purchase Master Manager"], first_name="Buyer").name

		with self.set_user(buyer):
			draft = frappe.get_doc(
				{
					"doctype": REQUEST,
					"party_type": "Supplier",
					"onboarding_template": SUPPLIER_TEMPLATE,
					"party_name": "Desk Traders " + frappe.generate_hash(length=6),
				}
			).insert()
			self.assertIn(draft.name, frappe.get_list(REQUEST, pluck="name"))

		with self.set_user(other_buyer):
			self.assertNotIn(draft.name, frappe.get_list(REQUEST, pluck="name"))

	def test_a_brand_new_signup_holds_no_party_role(self):
		"""The premise: the Supplier or Customer role is the outcome of approval, not a prerequisite."""
		applicant = self.make_applicant()
		self.assertEqual(set(frappe.get_roles(applicant)), {"All", "Guest"})

	def test_a_brand_new_signup_can_apply_as_either(self):
		applicant = self.make_applicant()

		with self.set_user(applicant):
			session = get_session()
			self.assertTrue(session["can_apply"])
			self.assertTrue(session["is_applicant"])
			self.assertEqual(set(session["open_party_types"]), {"Supplier", "Customer"})

			for party_type in ("Supplier", "Customer"):
				saved = save_application(self.base_values(party_type))
				self.assertEqual(saved["party_type"], party_type)
				self.assertEqual(frappe.db.get_value(REQUEST, saved["name"], "owner"), applicant)

	def test_the_party_type_is_never_chosen_for_them(self):
		"""An application saved before choosing stays unchosen — no silent Supplier default."""
		with self.set_user(self.make_applicant()):
			saved = save_application({"party_name": "Undecided Ltd"})

		self.assertFalse(saved["party_type"])
		self.assertFalse(frappe.db.get_value(REQUEST, saved["name"], "party_type"))

	def test_a_closed_party_type_cannot_be_chosen(self):
		with self.closed("Customer"), self.set_user(self.make_applicant()):
			self.assertEqual(get_session()["open_party_types"], ["Supplier"])
			self.assertRaises(frappe.ValidationError, save_application, self.base_values("Customer"))

	def test_a_draft_cannot_be_submitted_once_its_party_type_closes(self):
		applicant = self.make_applicant()
		saved = self.complete(applicant, "Customer")

		with self.closed("Customer"), self.set_user(applicant):
			self.assertRaises(frappe.ValidationError, submit_application, saved["name"])

	def test_nothing_open_means_nothing_to_apply_for(self):
		with self.closed("Supplier"), self.closed("Customer"), self.set_user(self.make_applicant()):
			self.assertFalse(get_session()["can_apply"])
			self.assertEqual(get_onboarding_types(), [])

	def test_onboarding_types_carry_their_party_and_only_its_documents(self):
		with self.set_user(self.make_applicant()):
			types = {t["name"]: t for t in get_onboarding_types()}

		supplier, customer = types[SUPPLIER_TEMPLATE], types[CUSTOMER_TEMPLATE]
		self.assertEqual(supplier["party_type"], "Supplier")
		self.assertEqual(customer["party_type"], "Customer")

		supplier_docs = [d["document_type"] for d in supplier["documents"]]
		self.assertIn(DOC_CERT, supplier_docs)
		self.assertIn(DOC_OPTIONAL, supplier_docs)
		self.assertNotIn(DOC_RETIRED, supplier_docs, "a disabled document type must not be asked for")
		self.assertIn(DOC_CUSTOMER_ONLY, [d["document_type"] for d in customer["documents"]])

	def test_a_closed_party_types_onboarding_types_are_hidden(self):
		with self.closed("Supplier"), self.set_user(self.make_applicant()):
			self.assertEqual({t["party_type"] for t in get_onboarding_types()}, {"Customer"})

	def test_the_role_arrives_only_on_approval(self):
		"""No role -> apply -> approved -> the role and the party appear, for either party type."""
		for party_type in ("Supplier", "Customer"):
			applicant = self.make_applicant()
			submitted = self.complete_and_submit(applicant, party_type)
			self.assertNotIn(party_type, frappe.get_roles(applicant))

			party = frappe.get_doc(REQUEST, submitted["name"]).approve()

			frappe.clear_cache(user=applicant)
			self.assertIn(party_type, frappe.get_roles(applicant), "approval grants the role")

			with self.set_user(applicant):
				parties = get_linked_parties()
				self.assertFalse(get_session()["is_applicant"])

			self.assertEqual([(p["party_type"], p["name"]) for p in parties], [(party_type, party)])

	def test_one_account_can_become_both_supplier_and_customer(self):
		applicant = self.make_applicant()
		values = self.base_values()

		for party_type in ("Supplier", "Customer"):
			submitted = self.complete_and_submit(
				applicant,
				party_type,
				{"party_name": values["party_name"], "tax_id": values["tax_id"]},
			)
			frappe.get_doc(REQUEST, submitted["name"]).approve()

		frappe.clear_cache(user=applicant)
		with self.set_user(applicant):
			held = {p["party_type"] for p in get_linked_parties()}

		self.assertEqual(held, {"Supplier", "Customer"})

	def test_company_logo_carries_through_to_the_party(self):
		applicant = self.make_applicant()
		saved = self.complete(applicant, "Customer")

		with self.set_user(applicant):
			logo = save_attachment(saved["name"], "logo.png", self.png(), None)
			saved = save_application({"company_logo": logo["file_url"]}, saved["name"])
			self.assertEqual(saved["company_logo"], logo["file_url"])
			submit_application(saved["name"])

		customer = frappe.get_doc(REQUEST, saved["name"]).approve()
		self.assertEqual(frappe.db.get_value("Customer", customer, "image"), logo["file_url"])

	def png(self):
		return base64.b64decode(
			"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
		)

	def test_contact_and_address_are_mandatory_whatever_the_party_type(self):
		"""Not template driven: we cannot work with a party we cannot contact or post to."""
		for party_type in ("Supplier", "Customer"):
			applicant = self.make_applicant()
			saved = self.complete(applicant, party_type)
			with self.set_user(applicant):
				save_application({"contacts": [], "addresses": []}, saved["name"])
				progress = get_application_progress(saved["name"])
				self.assertFalse(progress["can_submit"])
				self.assertIn("A primary contact", progress["missing_details"])
				self.assertIn("A billing address", progress["missing_details"])
				self.assertRaises(frappe.ValidationError, submit_application, saved["name"])

	def test_mobile_number_is_mandatory(self):
		applicant = self.make_applicant()
		saved = self.complete(applicant)
		with self.set_user(applicant):
			save_application({"contacts": [self.contact(mobile_no=None)]}, saved["name"])
			self.assertRaises(frappe.ValidationError, submit_application, saved["name"])

	def test_a_customer_must_say_where_to_deliver(self):
		applicant = self.make_applicant()
		saved = self.complete(applicant, "Customer")
		with self.set_user(applicant):
			save_application({"addresses": [self.address(is_shipping_address=0)]}, saved["name"])
			self.assertIn("A delivery address", get_application_progress(saved["name"])["missing_details"])
			self.assertRaises(frappe.ValidationError, submit_application, saved["name"])

	def test_a_customer_can_deliver_somewhere_other_than_their_registered_address(self):
		applicant = self.make_applicant()
		depot = self.address(
			address_type="Shipping", address_line1="9 Depot Lane", is_primary_address=0, is_shipping_address=1
		)
		submitted = self.complete_and_submit(
			applicant, "Customer", {"addresses": [self.address(is_shipping_address=0), depot]}
		)

		request = frappe.get_doc(REQUEST, submitted["name"])
		request.approve()
		request.reload()

		registered, delivery = request.addresses
		self.assertFalse(frappe.db.get_value("Address", registered.address, "is_shipping_address"))
		self.assertTrue(frappe.db.get_value("Address", delivery.address, "is_shipping_address"))

	def test_the_primary_contact_does_billing_by_default(self):
		submitted = self.complete_and_submit(self.make_applicant())

		request = frappe.get_doc(REQUEST, submitted["name"])
		request.approve()
		request.reload()

		self.assertEqual(len(request.contacts), 1, "no second contact when none was asked for")
		self.assertTrue(frappe.db.get_value("Contact", request.contacts[0].contact, "is_billing_contact"))

	def test_a_separate_billing_contact_is_created_when_asked_for(self):
		billing = {
			"first_name": "Brenda",
			"last_name": "Achieng",
			"email_id": "accounts@example.com",
			"is_billing_contact": 1,
		}
		submitted = self.complete_and_submit(
			self.make_applicant(), "Customer", {"contacts": [self.contact(), billing]}
		)

		request = frappe.get_doc(REQUEST, submitted["name"])
		request.approve()
		request.reload()

		primary, accounts = request.contacts
		self.assertNotEqual(primary.contact, accounts.contact)
		self.assertTrue(frappe.db.get_value("Contact", accounts.contact, "is_billing_contact"))
		self.assertFalse(
			frappe.db.get_value("Contact", primary.contact, "is_billing_contact"),
			"the primary contact steps aside when a billing contact is named",
		)

	def test_a_separate_billing_contact_needs_its_own_details(self):
		applicant = self.make_applicant()
		saved = self.complete(applicant)
		with self.set_user(applicant):
			save_application({"contacts": [self.contact(), {"is_billing_contact": 1}]}, saved["name"])
			self.assertRaises(frappe.ValidationError, submit_application, saved["name"])

	def test_row_fields_outside_the_contract_are_ignored(self):
		"""A crafted row cannot point the request at an existing Contact or Address."""
		contact = frappe.get_all("Contact", limit=1, pluck="name")
		address = frappe.get_all("Address", limit=1, pluck="name")

		with self.set_user(self.make_applicant()):
			saved = save_application(
				{
					**self.base_values(),
					"contacts": [self.contact(contact=contact[0] if contact else "X")],
					"addresses": [self.address(address=address[0] if address else "X")],
				}
			)

		request = frappe.get_doc(REQUEST, saved["name"])
		self.assertIsNone(request.contacts[0].contact)
		self.assertIsNone(request.addresses[0].address)

	def test_address_types_are_limited_to_portal_ones(self):
		with self.set_user(self.make_applicant()):
			saved = save_application(
				{**self.base_values(), "addresses": [self.address(address_type="Personal")]}
			)

		self.assertEqual(saved["addresses"][0]["address_type"], "Billing")

	def test_draft_may_be_incomplete_and_resumed(self):
		applicant = self.make_applicant()
		with self.set_user(applicant):
			first = save_application({"party_type": "Customer", "party_name": "Half Done"})
			self.assertIsNone(first["tax_id"])

			resumed = get_application()
			self.assertEqual(resumed["name"], first["name"])
			self.assertEqual(resumed["party_name"], "Half Done")
			self.assertEqual(resumed["party_type"], "Customer")

	def test_save_records_the_applicant(self):
		applicant = self.make_applicant()
		with self.set_user(applicant):
			saved = save_application(self.base_values())

		self.assertEqual(saved["docstatus"], 0)
		self.assertEqual(frappe.db.get_value(REQUEST, saved["name"], "applicant_user"), applicant)

	def test_checklist_comes_from_the_chosen_onboarding_type(self):
		with self.set_user(self.make_applicant()):
			saved = save_application(self.base_values("Customer"))

		names = [d["document_type"] for d in saved["documents"]]
		self.assertEqual(names, [DOC_CERT, DOC_CUSTOMER_ONLY])

	def test_progress_reports_what_is_outstanding(self):
		with self.set_user(self.make_applicant()):
			saved = save_application(self.base_values())
			progress = get_application_progress(saved["name"])

		self.assertFalse(progress["can_submit"])
		self.assertIn(f"{DOC_CERT}: not attached", progress["missing_documents"])
		self.assertEqual(progress["documents_required"], 1)
		self.assertEqual(progress["documents_attached"], 0)

	def test_submit_blocked_until_required_documents_are_attached(self):
		with self.set_user(self.make_applicant()):
			saved = save_application(self.base_values())
			self.assertRaises(frappe.ValidationError, submit_application, saved["name"])

	def test_full_application_submits_and_locks(self):
		applicant = self.make_applicant()
		saved = self.complete(applicant, "Customer")

		with self.set_user(applicant):
			self.assertTrue(get_application_progress(saved["name"])["can_submit"])
			submitted = submit_application(saved["name"])
			self.assertRaises(
				frappe.ValidationError, save_application, {"party_name": "Changed"}, saved["name"]
			)

		self.assertEqual(submitted["docstatus"], 1)
		self.assertEqual(submitted["onboarding_status"], "Pending Review")
		self.assertFalse(submitted["can_edit"])

	def returned(self, applicant, party_type="Supplier"):
		submitted = self.complete_and_submit(applicant, party_type)
		frappe.get_doc(REQUEST, submitted["name"]).return_for_correction(reason="Fix.")
		return submitted

	def test_returning_for_correction_reopens_the_same_application(self):
		applicant = self.make_applicant()
		submitted = self.returned(applicant)

		request = frappe.get_doc(REQUEST, submitted["name"])
		self.assertEqual(request.docstatus, 1, "the request stays submitted")

		with self.set_user(applicant):
			view = get_application(submitted["name"])

		self.assertTrue(view["can_edit"], "a returned request is editable again")
		self.assertTrue(view["is_correction"])

	def test_correcting_updates_the_original_and_returns_it_to_review(self):
		applicant = self.make_applicant()
		submitted = self.returned(applicant, "Customer")

		with self.set_user(applicant):
			out = resubmit_application(submitted["name"], {"party_name": "Corrected Traders"})

		self.assertEqual(out["name"], submitted["name"], "same document, not an amendment")
		self.assertEqual(out["party_name"], "Corrected Traders")
		self.assertEqual(out["onboarding_status"], "Pending Review")
		self.assertFalse(out["is_correction"])
		self.assertFalse(out["can_edit"], "locked again while it is with us")
		self.assertIsNone(frappe.db.get_value(REQUEST, submitted["name"], "review_remarks"))

	def test_a_correction_cannot_switch_party_type(self):
		applicant = self.make_applicant()
		submitted = self.returned(applicant, "Supplier")

		with self.set_user(applicant):
			self.assertRaises(
				frappe.ValidationError,
				resubmit_application,
				submitted["name"],
				{"party_type": "Customer", "onboarding_template": CUSTOMER_TEMPLATE},
			)

		self.assertEqual(frappe.db.get_value(REQUEST, submitted["name"], "party_type"), "Supplier")

	def test_a_correction_cannot_write_fields_outside_the_contract(self):
		"""A crafted payload must not reach status, the created party or the company."""
		applicant = self.make_applicant()
		submitted = self.returned(applicant)
		company = frappe.db.get_value(REQUEST, submitted["name"], "company")

		with self.set_user(applicant):
			resubmit_application(
				submitted["name"],
				{
					"party_name": "Still Legitimate Ltd",
					"onboarding_status": "Approved",
					"party": "INJECTED-PARTY",
					"company": "Bogus Co",
					"reviewed_by": "Administrator",
					"customer_group": "Bogus Group",
				},
			)

		row = frappe.db.get_value(
			REQUEST,
			submitted["name"],
			["party_name", "onboarding_status", "party", "company", "reviewed_by"],
			as_dict=True,
		)
		self.assertEqual(row.party_name, "Still Legitimate Ltd", "allowed field did change")
		self.assertEqual(row.onboarding_status, "Pending Review", "status is ours to set")
		self.assertIsNone(row.party)
		self.assertEqual(row.company, company)
		self.assertIsNone(row.reviewed_by)

	def test_the_portal_opens_a_returned_request_rather_than_a_blank_form(self):
		applicant = self.make_applicant()
		submitted = self.returned(applicant)

		with self.set_user(applicant):
			opened = get_application()

		self.assertEqual(opened["name"], submitted["name"])
		self.assertTrue(opened["is_correction"])

	def test_correcting_does_not_create_a_second_request(self):
		applicant = self.make_applicant()
		self.returned(applicant)

		with self.set_user(applicant):
			opened = get_application()
			save_application({"party_name": "Edited Once"}, opened["name"])
			resubmit_application(opened["name"], {"party_name": "Edited Twice"})

		self.assertEqual(frappe.db.count(REQUEST, {"owner": applicant}), 1)

	def test_a_draft_still_wins_over_a_returned_request(self):
		applicant = self.make_applicant()
		self.returned(applicant)

		with self.set_user(applicant):
			draft = save_application({**self.base_values(), "party_name": "A newer draft"})
			self.assertEqual(get_application()["name"], draft["name"])

	def test_only_a_returned_application_can_be_resubmitted(self):
		applicant = self.make_applicant()
		submitted = self.complete_and_submit(applicant)

		with self.set_user(applicant):
			self.assertRaises(frappe.ValidationError, resubmit_application, submitted["name"], {})

	def test_submitting_a_returned_request_puts_it_back_in_review(self):
		"""The portal's submit button on a correction must not leave it at Returned."""
		applicant = self.make_applicant()
		submitted = self.returned(applicant)

		with self.set_user(applicant):
			out = submit_application(submitted["name"])

		self.assertEqual(out["onboarding_status"], "Pending Review")

	def test_a_correction_still_needs_its_mandatory_documents(self):
		applicant = self.make_applicant()
		submitted = self.returned(applicant)

		with self.set_user(applicant):
			self.assertRaises(
				frappe.ValidationError,
				resubmit_application,
				submitted["name"],
				{"documents": [{"document_type": DOC_CERT, "attachment": None}]},
			)

	def test_an_applicant_with_no_roles_can_upload_a_document(self):
		"""Frappe's upload_file needs write permission; a fresh signup has none."""
		applicant = self.make_applicant()

		with self.set_user(applicant):
			saved = save_application(self.base_values())
			file = self.upload(saved["name"])

		self.assertEqual(file["attached_to_name"], saved["name"])
		self.assertEqual(frappe.db.get_value("File", file["name"], "owner"), applicant)
		self.assertTrue(file["is_private"])

	def test_an_applicant_cannot_upload_to_anothers_application(self):
		owner = self.make_applicant()
		with self.set_user(owner):
			saved = save_application(self.base_values())

		with self.set_user(self.make_applicant()):
			self.assertRaises(frappe.PermissionError, self.upload, saved["name"])

	def test_uploads_follow_the_allowed_file_types(self):
		with self.set_user(self.make_applicant()):
			saved = save_application(self.base_values())
			self.assertRaises(
				frappe.ValidationError, save_attachment, saved["name"], "run.exe", b"MZ", DOC_CERT
			)

	def test_a_file_from_someone_elses_application_cannot_be_named(self):
		"""Private URLs are guessable filenames; naming one must not borrow another business's certificate."""
		victim = self.make_applicant()
		with self.set_user(victim):
			theirs = save_application(self.base_values())
			certificate = self.upload(theirs["name"])

		with self.set_user(self.make_applicant()):
			mine = save_application(self.base_values())
			self.assertRaises(
				frappe.ValidationError,
				save_application,
				{"documents": [{"document_type": DOC_CERT, "attachment": certificate["file_url"]}]},
				mine["name"],
			)
			self.assertRaises(
				frappe.ValidationError,
				save_application,
				{"company_logo": certificate["file_url"]},
				mine["name"],
			)

	def test_the_same_certificate_may_back_both_applications(self):
		"""Identical files share a stored blob; each reviewer can still approve their own side."""
		applicant = self.make_applicant()
		sales = make_test_user(["Sales Master Manager"], first_name="Sales")

		supplier = self.complete_and_submit(applicant, "Supplier")
		frappe.get_doc(REQUEST, supplier["name"]).approve()
		customer = self.complete_and_submit(applicant, "Customer")

		with self.set_user(sales.name):
			frappe.get_doc(REQUEST, customer["name"]).approve()

		self.assertEqual(frappe.db.get_value(REQUEST, customer["name"], "onboarding_status"), "Approved")

	def test_link_lookups_serve_the_allowlisted_doctypes(self):
		with self.set_user(self.make_applicant()):
			countries = get_link_options("Country")
			self.assertRaises(frappe.PermissionError, get_link_options, "Bank")

		self.assertTrue(countries)
		self.assertEqual(set(countries[0]), {"label", "value"})

	def test_link_lookups_refuse_any_doctype_off_the_allowlist(self):
		"""get_all here skips permissions, so the allowlist is the only thing between a caller and any table."""
		with self.set_user(self.make_applicant()):
			for asked in (
				"User",
				"Sales Invoice",
				"Party Onboarding Request",
				"Party Onboarding Template",
				"country",
				"<b>x</b>",
			):
				self.assertRaises(frappe.PermissionError, get_link_options, asked)

	def test_the_refusal_does_not_echo_what_was_asked(self):
		with self.set_user(self.make_applicant()):
			frappe.local.message_log = []
			self.assertRaises(frappe.PermissionError, get_link_options, "Secret Doctype")
			self.assertNotIn("Secret Doctype", str(frappe.local.message_log))

	def test_guests_cannot_look_anything_up(self):
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, get_link_options, "Country")

	def test_an_applicant_only_sees_their_own_applications(self):
		first, second = self.make_applicant(), self.make_applicant()

		with self.set_user(first):
			mine = save_application(self.base_values())
		with self.set_user(second):
			theirs = save_application(self.base_values("Customer"))
			visible = {row["name"]: row for row in get_my_applications()}

		self.assertIn(theirs["name"], visible)
		self.assertEqual(visible[theirs["name"]]["party_type"], "Customer")
		self.assertNotIn(mine["name"], visible, "one applicant must not see another's application")

	def test_applicants_hold_no_frappe_read_on_requests(self):
		"""Reads go through the owner-scoped portal API only — nothing via /api/resource or get_list."""
		applicant = self.make_applicant()
		with self.set_user(applicant):
			mine = save_application(self.base_values())
			self.assertFalse(frappe.has_permission(REQUEST, "read"))
			self.assertFalse(frappe.get_doc(REQUEST, mine["name"]).has_permission("read"))
			self.assertRaises(frappe.PermissionError, frappe.get_list, REQUEST)
			self.assertIn(mine["name"], [row["name"] for row in get_my_applications()])

	def test_approved_parties_cannot_write_requests_around_the_portal_api(self):
		"""Supplier and Customer roles once carried write, create and submit — a way past the field whitelist."""
		for party_type in ("Supplier", "Customer"):
			applicant = self.make_applicant()
			submitted = self.complete_and_submit(applicant, party_type)
			frappe.get_doc(REQUEST, submitted["name"]).approve()
			frappe.clear_cache(user=applicant)
			self.assertIn(party_type, frappe.get_roles(applicant))

			with self.set_user(applicant):
				for ptype in ("create", "write", "submit"):
					self.assertFalse(frappe.has_permission(REQUEST, ptype), f"{party_type} {ptype}")

				crafted = frappe.get_doc(
					{**self.base_values(party_type), "doctype": REQUEST, "payment_terms": "Anything"}
				)
				self.assertRaises(frappe.PermissionError, crafted.insert)

				self.assertIn(
					submitted["name"], [row["name"] for row in get_my_applications()], "still sees their own"
				)

	def test_an_applicant_cannot_open_someone_elses_application(self):
		with self.set_user(self.make_applicant()):
			mine = save_application(self.base_values())

		with self.set_user(self.make_applicant()):
			self.assertRaises(frappe.PermissionError, get_application, mine["name"])

	def test_one_applicant_cannot_correct_anothers_application(self):
		submitted = self.returned(self.make_applicant())

		with self.set_user(self.make_applicant()):
			self.assertRaises(frappe.PermissionError, resubmit_application, submitted["name"], {})

	def test_applicant_cannot_reach_the_review_actions(self):
		"""approve/reject/return are absent from the portal API and barred by role."""
		for party_type in ("Supplier", "Customer"):
			applicant = self.make_applicant()
			submitted = self.complete_and_submit(applicant, party_type)

			with self.set_user(applicant):
				doc = frappe.get_doc(REQUEST, submitted["name"])
				self.assertRaises(frappe.PermissionError, doc.approve)
				self.assertRaises(frappe.PermissionError, doc.reject, reason="nope")

	def test_the_applicant_gets_their_own_application(self):
		applicant = self.make_applicant()
		saved = self.complete(applicant)

		with self.set_user(applicant):
			own = get_own_application(saved["name"])

		self.assertEqual(own.name, saved["name"])
		self.assertEqual(own.owner, applicant)

	def test_nobody_else_can_download_an_application(self):
		owner = self.make_applicant()
		saved = self.complete(owner)
		stranger = self.make_applicant()

		with self.set_user(stranger):
			self.assertRaises(frappe.PermissionError, get_own_application, saved["name"])
			self.assertRaises(frappe.PermissionError, download_application, saved["name"])

	def test_each_document_carries_its_rules_to_the_portal(self):
		self.require_expiry()
		applicant = self.make_applicant()
		saved = self.complete(applicant)

		with self.set_user(applicant):
			documents = {row["document_type"]: row for row in get_application(saved["name"])["documents"]}

		self.assertTrue(documents[DOC_CERT]["has_expiry"])
		self.assertFalse(documents[DOC_OPTIONAL]["has_expiry"])
		self.assertIn("allowed_file_types", documents[DOC_CERT])
		self.assertTrue(documents[DOC_CERT]["file_name"])

	def test_a_document_that_expires_needs_an_expiry_date(self):
		self.require_expiry()
		applicant = self.make_applicant()
		saved = self.complete(applicant)

		with self.set_user(applicant):
			progress = get_application_progress(saved["name"])
			self.assertFalse(progress["can_submit"])
			self.assertIn(f"{DOC_CERT}: expiry date", progress["missing_documents"])
			self.assertRaises(frappe.ValidationError, submit_application, saved["name"])

	def test_an_expired_document_blocks_submission(self):
		self.require_expiry()
		applicant = self.make_applicant()
		saved = self.complete(applicant)

		with self.set_user(applicant):
			save_application(
				{"documents": self.certificate(saved, expiry_date=add_days(today(), -1))}, saved["name"]
			)
			progress = get_application_progress(saved["name"])
			self.assertTrue(any("expired" in item for item in progress["missing_documents"]))
			self.assertRaises(frappe.ValidationError, submit_application, saved["name"])

	def test_a_current_expiry_date_lets_the_application_through(self):
		self.require_expiry()
		applicant = self.make_applicant()
		saved = self.complete(applicant)

		with self.set_user(applicant):
			save_application(
				{
					"documents": self.certificate(
						saved, issue_date=add_days(today(), -30), expiry_date=add_days(today(), 300)
					)
				},
				saved["name"],
			)
			self.assertTrue(get_application_progress(saved["name"])["can_submit"])
			self.assertEqual(submit_application(saved["name"])["onboarding_status"], "Pending Review")

	def test_an_issue_date_cannot_be_in_the_future(self):
		applicant = self.make_applicant()
		saved = self.complete(applicant)

		with self.set_user(applicant):
			save_application(
				{"documents": self.certificate(saved, issue_date=add_days(today(), 5))}, saved["name"]
			)
			self.assertFalse(get_application_progress(saved["name"])["can_submit"])
			self.assertRaises(frappe.ValidationError, submit_application, saved["name"])

	def test_the_upload_method_only_works_after_a_real_upload(self):
		applicant = self.make_applicant()
		with self.set_user(applicant):
			saved = save_application(self.base_values())
			frappe.local.form_dict = frappe._dict(application=saved["name"], document_type=DOC_CERT)
			self.assertRaises(frappe.ValidationError, attach_uploaded_file)

	def test_a_logo_must_be_an_image(self):
		applicant = self.make_applicant()
		with self.set_user(applicant):
			saved = save_application(self.base_values())
			self.assertRaises(
				frappe.ValidationError, self.upload, saved["name"], "logo.pdf", None, None, "logo"
			)

	def test_a_supplier_gives_only_a_billing_address(self):
		"""Suppliers are not asked where goods go; a second address is refused."""
		warehouse = self.address(address_type="Warehouse", is_primary_address=0)
		with self.set_user(self.make_applicant()):
			self.assertRaises(
				frappe.ValidationError,
				save_application,
				{**self.base_values(), "addresses": [self.address(), warehouse]},
			)

	def test_a_supplier_can_submit_with_just_a_billing_address(self):
		"""No delivery address is outstanding for a supplier."""
		applicant = self.make_applicant()
		saved = self.complete(applicant)
		with self.set_user(applicant):
			progress = get_application_progress(saved["name"])

		self.assertNotIn("A delivery address", progress["missing_details"])
		self.assertTrue(progress["can_submit"])

	def test_extra_customer_addresses_become_delivery_addresses(self):
		"""Every address after the billing one is saved as a delivery address."""
		branch = self.address(address_type="Office", is_primary_address=0, is_shipping_address=0)
		with self.set_user(self.make_applicant()):
			saved = save_application(
				{**self.base_values("Customer"), "addresses": [self.address(address_type="Shop"), branch]}
			)

		billing, delivery = saved["addresses"]
		self.assertEqual(billing["address_type"], "Billing")
		self.assertEqual(delivery["address_type"], "Shipping")
		self.assertTrue(delivery["is_shipping_address"])

	def test_only_a_primary_and_a_billing_contact_are_collected(self):
		"""A third contact is refused; more people can be added after approval."""
		contacts = [
			self.contact(),
			self.contact(is_primary_contact=0, is_billing_contact=1, email_id="billing@example.com"),
			self.contact(is_primary_contact=0, email_id="other@example.com"),
		]
		with self.set_user(self.make_applicant()):
			self.assertRaises(
				frappe.ValidationError, save_application, {**self.base_values(), "contacts": contacts}
			)

	def test_contact_rows_that_are_not_objects_are_refused(self):
		"""A tampered request with a list of strings is rejected rather than half-saved."""
		with self.set_user(self.make_applicant()):
			self.assertRaises(
				frappe.ValidationError, save_application, {**self.base_values(), "contacts": ["x"]}
			)

	def test_tax_number_formats_are_shared_with_the_portal(self):
		"""The portal checks the KRA PIN with the same pattern the server enforces."""
		with self.set_user(self.make_applicant()):
			formats = get_tax_id_formats().data

		self.assertEqual(formats["Kenya"]["example"], "P051234567X")

	def test_a_bad_kra_pin_is_refused_on_save(self):
		"""The server rejects a malformed KRA PIN even if the portal check was skipped."""
		with self.set_user(self.make_applicant()):
			self.assertRaises(
				frappe.ValidationError,
				save_application,
				{**self.base_values(), "country": "Kenya", "tax_id": "A12"},
			)

	def test_guests_cannot_read_tax_number_formats(self):
		"""The format list is for signed-in applicants only."""
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, get_tax_id_formats)

	def test_the_billing_address_does_not_count_as_a_delivery_address(self):
		"""A customer must give a delivery address of its own, even if it matches the billing one."""
		applicant = self.make_applicant()
		with self.set_user(applicant):
			saved = save_application(
				{**self.base_values("Customer"), "addresses": [self.address(is_shipping_address=1)]}
			)
			progress = get_application_progress(saved["name"])

		self.assertFalse(saved["addresses"][0]["is_shipping_address"])
		self.assertIn("A delivery address", progress["missing_details"])
