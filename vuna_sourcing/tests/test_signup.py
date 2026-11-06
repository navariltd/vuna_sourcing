# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.website.utils import get_home_page

from vuna_sourcing import APP_NAME
from vuna_sourcing.api.permission import (
	PORTAL_USER_ROLE,
	clear_portal_default_app,
	has_app_permission,
	portal_home_page,
)
from vuna_sourcing.api.response import ApiResponse, ResponseStatus
from vuna_sourcing.api.signup import get_signup_context, sign_up
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.utils import get_app_branding


class TestSignup(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.local.request_ip = None
		self.open_registration()
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")

	def open_registration(self, mode="Open to Public", party_types=("Supplier", "Customer")):
		frappe.db.set_single_value(
			"Sourcing Settings",
			{
				"registration_mode": mode,
				"accept_supplier_applications": int("Supplier" in party_types),
				"accept_customer_applications": int("Customer" in party_types),
			},
		)
		frappe.clear_cache()

	def new_email(self):
		return f"{frappe.generate_hash(length=10)}@example.com"

	def test_branding_is_read_from_hooks(self):
		branding = get_app_branding()
		entry = frappe.get_hooks("add_to_apps_screen", app_name=APP_NAME)[0]

		self.assertEqual(branding["name"], APP_NAME)
		self.assertEqual(branding["title"], entry["title"])
		self.assertEqual(branding["logo"], entry["logo"])
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

	def test_staff_who_manage_sourcing_can_invite_while_registration_is_closed(self):
		self.open_registration(mode="Invitation Only")
		buyer = make_test_user(["Purchase Master Manager"], first_name="Buyer").name
		email = self.new_email()

		with self.set_user(buyer):
			result = sign_up("Amina", "Otieno", email)

		self.assertTrue(result.ok, result.message)
		self.assertIn(PORTAL_USER_ROLE, frappe.get_roles(email))

	def test_staff_without_settings_access_cannot_invite(self):
		self.open_registration(mode="Invitation Only")
		clerk = make_test_user(["Purchase User"], first_name="Clerk").name
		email = self.new_email()

		with self.set_user(clerk):
			result = sign_up("Amina", "Otieno", email)

		self.assertFalse(result.ok)
		self.assertFalse(frappe.db.exists("User", email))

	def test_invitation_only_creates_no_account(self):
		self.open_registration(mode="Invitation Only")
		email = self.new_email()

		sign_up("Amina", "Otieno", email)
		self.assertFalse(frappe.db.exists("User", email))

	def test_site_wide_signup_switch_does_not_close_registration(self):
		frappe.db.set_single_value("Website Settings", "disable_signup", 1)
		frappe.clear_cache()

		self.assertTrue(get_signup_context().data.is_open)
		result = sign_up("Amina", "Otieno", self.new_email())
		self.assertTrue(result.ok, result.message)

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
		self.assertFalse(user.default_app, "their role home page sends them to the portal, not the desk")

	def test_a_new_signup_holds_the_portal_role(self):
		"""The key to the portal, granted at signup — approval is what adds Supplier or Customer."""
		email = self.new_email()
		sign_up("Amina", "Otieno", email)

		self.assertIn(PORTAL_USER_ROLE, frappe.get_roles(email))
		with self.set_user(email):
			self.assertFalse(has_app_permission(), "the desk app icon is for staff, not portal users")

	def test_the_desk_app_icon_opens_the_sourcing_workspace_for_staff(self):
		"""Staff see the app on the apps screen and it opens the desk; portal users land on the portal."""
		entry = frappe.get_hooks("add_to_apps_screen", app_name=APP_NAME)[0]
		staff = frappe.get_doc(
			{
				"doctype": "User",
				"email": self.new_email(),
				"first_name": "Staff",
				"send_welcome_email": 0,
				"roles": [{"role": "Purchase User"}],
			}
		).insert(ignore_permissions=True)

		self.assertEqual(entry["route"], "/desk/sourcing")
		with self.set_user(staff.name):
			self.assertTrue(has_app_permission())

	def test_portal_users_land_on_the_portal_and_staff_on_the_desk(self):
		"""Only website users are sent to the portal; staff holding the portal role still land on the desk."""
		portal_user = self.new_email()
		sign_up("Amina", "Otieno", portal_user)
		staff = frappe.get_doc(
			{
				"doctype": "User",
				"email": self.new_email(),
				"first_name": "Staff",
				"send_welcome_email": 0,
				"roles": [{"role": "Purchase User"}, {"role": PORTAL_USER_ROLE}, {"role": "Customer"}],
			}
		).insert(ignore_permissions=True)

		self.assertFalse(frappe.db.get_value("Role", PORTAL_USER_ROLE, "home_page"))
		self.assertEqual(portal_home_page(portal_user), "vuna-sourcing")
		self.assertIsNone(portal_home_page(staff.name))
		self.assertIsNone(portal_home_page("Administrator"))
		for user in (portal_user, staff.name):
			frappe.cache.hdel("home_page", user)
		with self.set_user(portal_user):
			self.assertEqual(get_home_page(), "vuna-sourcing")
		with self.set_user(staff.name):
			self.assertNotEqual(get_home_page(), "vuna-sourcing")

	def test_signing_in_clears_an_old_portal_default_app(self):
		"""Accounts made before the desk route existed still had the app as default; signing in clears it."""
		portal_user = self.new_email()
		sign_up("Amina", "Otieno", portal_user)
		frappe.db.set_value("User", portal_user, "default_app", APP_NAME)
		staff = frappe.get_doc(
			{
				"doctype": "User",
				"email": self.new_email(),
				"first_name": "Staff",
				"send_welcome_email": 0,
				"default_app": APP_NAME,
				"roles": [{"role": "Purchase User"}],
			}
		).insert(ignore_permissions=True)

		for user in (portal_user, staff.name):
			with self.set_user(user):
				clear_portal_default_app()

		self.assertFalse(frappe.db.get_value("User", portal_user, "default_app"))
		self.assertEqual(frappe.db.get_value("User", staff.name, "default_app"), APP_NAME)

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
