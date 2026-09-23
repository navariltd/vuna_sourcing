# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from vuna_sourcing import APP_NAME
from vuna_sourcing.api.permission import PORTAL_USER_ROLE, has_app_permission
from vuna_sourcing.api.response import ApiResponse, ResponseStatus
from vuna_sourcing.api.signup import get_signup_context, sign_up
from vuna_sourcing.utils import get_app_branding


class TestSignup(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		# The endpoint is rate limited per IP; tests run without one.
		frappe.local.request_ip = None
		self.open_registration()

	def open_registration(
		self, mode="Open to Public", site_signup_enabled=True, party_types=("Supplier", "Customer")
	):
		frappe.db.set_single_value(
			"Sourcing Settings",
			{
				"registration_mode": mode,
				"accept_supplier_applications": int("Supplier" in party_types),
				"accept_customer_applications": int("Customer" in party_types),
			},
		)
		frappe.db.set_single_value("Website Settings", "disable_signup", 0 if site_signup_enabled else 1)
		frappe.clear_cache()

	def new_email(self):
		return f"{frappe.generate_hash(length=10)}@example.com"

	# ------------------------------------------------------------------
	# Branding comes from hooks, not from a second copy of the truth
	# ------------------------------------------------------------------

	def test_branding_is_read_from_hooks(self):
		branding = get_app_branding()
		entry = frappe.get_hooks("add_to_apps_screen", app_name=APP_NAME)[0]

		self.assertEqual(branding["name"], APP_NAME)
		self.assertEqual(branding["title"], entry["title"])
		self.assertEqual(branding["logo"], entry["logo"])
		self.assertEqual(branding["route"], entry["route"])
		self.assertNotIn(
			"contact_email",
			branding,
			"the business's address belongs on Sourcing Settings, not in hooks",
		)

	def test_contact_email_comes_from_sourcing_settings(self):
		frappe.db.set_single_value("Sourcing Settings", "contact_email", "procurement@example.com")
		frappe.clear_cache()

		self.assertEqual(get_signup_context().data.contact_email, "procurement@example.com")

	def test_every_response_uses_the_shared_envelope(self):
		"""ok / status / message / data — the same four keys, whatever happened."""
		context = get_signup_context()
		created = sign_up("Amina", "Otieno", self.new_email())

		self.open_registration(mode="Invitation Only")
		refused = sign_up("Amina", "Otieno", self.new_email())

		for response in (context, created, refused):
			self.assertIsInstance(response, ApiResponse)
			self.assertEqual(set(response.as_dict()), {"ok", "status", "message", "data"})
			self.assertIn(response.status, (ResponseStatus.SUCCESS, ResponseStatus.ERROR))

		self.assertTrue(created.ok)
		self.assertFalse(refused.ok)

	def test_envelope_serialises_the_way_frappe_will_send_it(self):
		"""json_handler calls __json__, so the dataclass goes over the wire as JSON."""
		import json

		from frappe.utils.response import json_handler

		response = sign_up("Amina", "Otieno", self.new_email())
		payload = json.loads(json.dumps(response, default=json_handler))

		self.assertEqual(payload["status"], "success")
		self.assertTrue(payload["ok"])
		self.assertIsInstance(payload["message"], str)
		self.assertEqual(set(payload["data"]), {"email", "email_sent"})

	def test_signup_context_carries_branding(self):
		context = get_signup_context()

		self.assertTrue(context.ok)
		self.assertEqual(context.status, ResponseStatus.SUCCESS)
		self.assertTrue(context.data.is_open)
		self.assertIsNone(context.data.closed_message)
		self.assertEqual(context.data.logo, get_app_branding()["logo"])
		self.assertEqual(context.data.app_title, get_app_branding()["title"])

	# ------------------------------------------------------------------
	# The two gates
	# ------------------------------------------------------------------

	def test_signup_context_says_what_an_account_can_apply_as(self):
		self.assertEqual(get_signup_context().data.party_types, ["Supplier", "Customer"])

		self.open_registration(party_types=("Customer",))
		self.assertEqual(get_signup_context().data.party_types, ["Customer"])

	def test_no_open_party_type_closes_registration(self):
		"""An account with nothing to apply for would be a dead end."""
		self.open_registration(party_types=())

		context = get_signup_context()
		self.assertFalse(context.data.is_open)
		self.assertEqual(context.data.party_types, [])
		self.assertFalse(sign_up("Amina", "Otieno", self.new_email()).ok)

	def test_invitation_only_refuses_and_explains(self):
		self.open_registration(mode="Invitation Only")

		context = get_signup_context()
		self.assertFalse(context.data.is_open)
		self.assertIn("invitation", context.data.closed_message.lower())

		result = sign_up("Amina", "Otieno", self.new_email())
		self.assertFalse(result.ok)
		self.assertIn("invitation", result.message.lower())

	def test_invitation_only_creates_no_account(self):
		self.open_registration(mode="Invitation Only")
		email = self.new_email()

		sign_up("Amina", "Otieno", email)
		self.assertFalse(frappe.db.exists("User", email))

	def test_site_wide_signup_switch_also_closes_registration(self):
		"""Open to Public cannot override the site's own disable_signup."""
		self.open_registration(mode="Open to Public", site_signup_enabled=False)

		self.assertFalse(get_signup_context().data.is_open)
		result = sign_up("Amina", "Otieno", self.new_email())
		self.assertFalse(result.ok)

	# ------------------------------------------------------------------
	# Creating the account
	# ------------------------------------------------------------------

	def test_signup_creates_a_website_user_marked_for_this_app(self):
		email = self.new_email()
		result = sign_up("Amina", "Otieno", email)

		self.assertTrue(result.ok, result.message)

		user = frappe.get_doc("User", email)
		self.assertEqual(user.user_type, "Website User")
		self.assertEqual(user.first_name, "Amina")
		self.assertEqual(user.last_name, "Otieno")
		self.assertTrue(user.enabled)
		self.assertTrue(user.send_welcome_email)
		self.assertEqual(user.default_app, APP_NAME, "marks them as having come via the portal")

	def test_a_new_signup_holds_the_portal_role(self):
		"""The key to the portal, granted at signup — approval is what adds Supplier or Customer."""
		email = self.new_email()
		sign_up("Amina", "Otieno", email)

		self.assertIn(PORTAL_USER_ROLE, frappe.get_roles(email))
		with self.set_user(email):
			self.assertTrue(has_app_permission(), "and with it, the app on the apps screen")

	def test_a_new_signup_holds_no_party_role(self):
		email = self.new_email()
		sign_up("Amina", "Otieno", email)

		self.assertNotIn("Supplier", frappe.get_roles(email))
		self.assertNotIn("Customer", frappe.get_roles(email))

	def test_no_password_is_accepted_over_the_wire(self):
		"""The welcome email carries the link that sets it — that is the verification."""
		import inspect

		signature = inspect.signature(sign_up)
		self.assertEqual(list(signature.parameters), ["first_name", "last_name", "email"])

	# ------------------------------------------------------------------
	# Input handling
	# ------------------------------------------------------------------

	def test_duplicate_email_is_refused_kindly(self):
		email = self.new_email()
		sign_up("Amina", "Otieno", email)

		result = sign_up("Amina", "Otieno", email)
		self.assertFalse(result.ok)
		self.assertIn("already", result.message.lower())

	def test_disabled_account_gets_a_different_message(self):
		email = self.new_email()
		sign_up("Amina", "Otieno", email)
		frappe.db.set_value("User", email, "enabled", 0)

		result = sign_up("Amina", "Otieno", email)
		self.assertFalse(result.ok)
		self.assertIn("disabled", result.message.lower())

	def test_missing_names_are_rejected(self):
		self.assertRaises(frappe.ValidationError, sign_up, "", "Otieno", self.new_email())
		self.assertRaises(frappe.ValidationError, sign_up, "Amina", "", self.new_email())

	def test_invalid_email_is_rejected(self):
		self.assertRaises(frappe.ValidationError, sign_up, "Amina", "Otieno", "not-an-email")

	def test_email_is_normalised_and_names_trimmed(self):
		email = self.new_email().upper()
		sign_up("  Amina  ", "  Otieno  ", email)

		user = frappe.get_doc("User", email.lower())
		self.assertEqual(user.first_name, "Amina")
		self.assertEqual(user.last_name, "Otieno")

	def test_html_in_names_is_escaped(self):
		email = self.new_email()
		sign_up("<script>alert(1)</script>", "Otieno", email)

		first_name = frappe.db.get_value("User", email, "first_name")
		self.assertNotIn("<script>", first_name)
