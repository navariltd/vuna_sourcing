# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.permissions import AUTOMATIC_ROLES
from frappe.tests import IntegrationTestCase

from vuna_sourcing.api.portal import get_session
from vuna_sourcing.api.transactions.team import (
	get_team,
	invite_team_member,
	remove_team_member,
	resend_invitation,
	update_member_branches,
)
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures

SETTINGS = "Sourcing Settings"


class TestCustomerTeam(SourcingFixtures, IntegrationTestCase):
	"""A customer's account admin inviting and managing their own portal users."""

	def setUp(self):
		self.use_setting("allow_customer_team_management", 1)
		frappe.flags.mute_emails = True
		self.addCleanup(setattr, frappe.flags, "mute_emails", False)

		self.customer, self.admin = self.make_customer()
		self.set_admin(self.customer, self.admin)
		self.westlands = self.add_address("_Test Westlands")
		self.industrial = self.add_address("_Test Industrial Area")
		self.member = self.portal_user("John")
		self.add_member(self.member, [self.westlands])

	def portal_user(self, first_name):
		user = make_test_user(["Customer"], first_name=first_name, last_name="Doe").name
		frappe.db.set_value("User", user, "enabled", 1)
		return user

	def use_setting(self, field, value):
		current = frappe.db.get_single_value(SETTINGS, field)
		self.addCleanup(frappe.db.set_single_value, SETTINGS, field, current)
		frappe.db.set_single_value(SETTINGS, field, value)

	def set_admin(self, customer, user):
		doc = frappe.get_doc("Customer", customer)
		next(row for row in doc.portal_users if row.user == user).is_account_admin = 1
		doc.save(ignore_permissions=True)

	def add_member(self, user, branches=(), is_admin=0):
		doc = frappe.get_doc("Customer", self.customer)
		doc.append(
			"portal_users", {"user": user, "branches": "\n".join(branches), "is_account_admin": is_admin}
		)
		doc.save(ignore_permissions=True)

	def add_address(self, title, address_type="Shipping"):
		return (
			frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": f"{title} {frappe.generate_hash(length=6)}",
					"address_type": address_type,
					"address_line1": f"{title} Road",
					"city": "Nairobi",
					"country": frappe.get_all("Country", limit=1, pluck="name")[0],
					"links": [{"link_doctype": "Customer", "link_name": self.customer}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def invite(self, email=None, branches=None, customer=None):
		return invite_team_member(
			customer or self.customer,
			"Jane",
			"Doe",
			email or f"{frappe.generate_hash(length=10)}@example.com",
			branches,
		)

	def row_of(self, user):
		return next(
			(row for row in frappe.get_doc("Customer", self.customer).portal_users if row.user == user), None
		)

	def test_an_admin_sees_their_team(self):
		"""The team lists the admin first, then members with the branches they can see."""
		with self.set_user(self.admin):
			members = get_team(self.customer).data["members"]

		self.assertEqual([m["user"] for m in members], [self.admin, self.member])
		self.assertTrue(members[0]["is_you"] and members[0]["is_account_admin"])
		self.assertFalse(members[0]["editable"])
		self.assertEqual([b["name"] for b in members[1]["branches"]], [self.westlands])
		self.assertTrue(members[1]["editable"])

	def test_an_admin_invites_someone_to_a_branch(self):
		"""Inviting creates a portal account, links it to the customer with the branch, and emails them."""
		email = f"{frappe.generate_hash(length=10)}@example.com"
		with self.set_user(self.admin):
			response = self.invite(email, [self.industrial])

		self.assertTrue(response.ok)
		self.assertEqual(
			set(frappe.get_roles(email)) - set(AUTOMATIC_ROLES), {"Sourcing Portal User", "Customer"}
		)
		self.assertEqual(self.row_of(email).branches, self.industrial)
		self.assertFalse(self.row_of(email).is_account_admin)
		self.assertTrue(
			frappe.db.exists("Email Queue Recipient", {"recipient": email}),
			"the welcome email asks them to set a password",
		)

	def test_an_invite_with_no_branches_gives_every_branch(self):
		"""Leaving branches empty gives the new person the whole customer account."""
		with self.set_user(self.admin):
			email = f"{frappe.generate_hash(length=10)}@example.com"
			self.invite(email)

		self.assertFalse(self.row_of(email).branches)

	def test_an_email_that_already_has_an_account_is_refused(self):
		"""Invites only create new accounts; an existing account is added by our team instead."""
		someone = self.portal_user("Someone")

		with self.set_user(self.admin):
			self.assertRaises(frappe.ValidationError, self.invite, someone)
			self.assertRaises(frappe.ValidationError, self.invite, self.member)

		self.assertIsNone(self.row_of(someone))

	def test_a_branch_must_be_a_delivery_address_of_this_customer(self):
		"""Billing addresses and other customers' addresses cannot be handed out."""
		billing = self.add_address("_Test Head Office", address_type="Billing")
		other, _other_admin = self.make_customer()
		elsewhere = frappe.get_doc("Address", self.add_address("_Test Elsewhere"))
		elsewhere.links[0].link_name = other
		elsewhere.save(ignore_permissions=True)

		with self.set_user(self.admin):
			self.assertRaises(frappe.ValidationError, self.invite, branches=[billing])
			self.assertRaises(frappe.ValidationError, self.invite, branches=[elsewhere.name])
			self.assertRaises(
				frappe.ValidationError, update_member_branches, self.customer, self.member, [billing]
			)

		self.assertEqual(self.row_of(self.member).branches, self.westlands)

	def test_a_member_who_is_not_an_admin_cannot_manage_the_team(self):
		"""Being on the team is not enough; the server checks the account admin flag on every call."""
		with self.set_user(self.member):
			self.assertRaises(frappe.PermissionError, get_team, self.customer)
			self.assertRaises(frappe.PermissionError, self.invite)
			self.assertRaises(frappe.PermissionError, remove_team_member, self.customer, self.admin)

	def test_an_admin_of_another_customer_cannot_manage_this_team(self):
		"""Admin rights are per customer account."""
		other, other_admin = self.make_customer()
		self.set_admin(other, other_admin)

		with self.set_user(other_admin):
			self.assertRaises(frappe.PermissionError, get_team, self.customer)
			self.assertRaises(frappe.PermissionError, self.invite)

	def test_the_team_is_off_unless_settings_allow_it(self):
		"""With the setting off, even an account admin cannot manage users, and the session hides it."""
		self.use_setting("allow_customer_team_management", 0)

		with self.set_user(self.admin):
			self.assertRaises(frappe.PermissionError, get_team, self.customer)
			self.assertRaises(frappe.PermissionError, self.invite)
			party = next(p for p in get_session()["parties"] if p["name"] == self.customer)

		self.assertFalse(party["can_manage_team"])

	def test_the_session_tells_admins_they_can_manage_the_team(self):
		"""Only the account admin is offered team management."""
		with self.set_user(self.admin):
			admin_party = next(p for p in get_session()["parties"] if p["name"] == self.customer)
		with self.set_user(self.member):
			member_party = next(p for p in get_session()["parties"] if p["name"] == self.customer)

		self.assertTrue(admin_party["can_manage_team"])
		self.assertFalse(member_party["can_manage_team"])

	def test_an_admin_changes_a_members_branches(self):
		"""Branches can be widened, narrowed, or cleared to give every branch."""
		with self.set_user(self.admin):
			update_member_branches(self.customer, self.member, [self.westlands, self.industrial])
			self.assertEqual(
				set(self.row_of(self.member).branches.splitlines()), {self.westlands, self.industrial}
			)
			update_member_branches(self.customer, self.member, [])

		self.assertFalse(self.row_of(self.member).branches)

	def test_admins_and_yourself_cannot_be_changed_from_the_portal(self):
		"""Admin access is set on the desk only, so the portal cannot change or remove an admin."""
		second_admin = self.portal_user("Second")
		self.add_member(second_admin, is_admin=1)

		with self.set_user(self.admin):
			self.assertRaises(frappe.ValidationError, remove_team_member, self.customer, self.admin)
			self.assertRaises(frappe.ValidationError, remove_team_member, self.customer, second_admin)
			self.assertRaises(
				frappe.ValidationError, update_member_branches, self.customer, second_admin, [self.westlands]
			)

		self.assertTrue(self.row_of(second_admin).is_account_admin)

	def test_removing_a_member_ends_their_access(self):
		"""Removing the last link disables a portal-only account; the timeline records who did it."""
		with self.set_user(self.admin):
			remove_team_member(self.customer, self.member)

		self.assertIsNone(self.row_of(self.member))
		self.assertEqual(frappe.db.get_value("User", self.member, "enabled"), 0)
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "Customer",
					"reference_name": self.customer,
					"content": ("like", "%removed%"),
				},
			)
		)

	def test_a_member_of_another_customer_keeps_their_account_when_removed(self):
		"""Someone who also works for another customer stays enabled there."""
		other, _other_admin = self.make_customer()
		doc = frappe.get_doc("Customer", other)
		doc.append("portal_users", {"user": self.member})
		doc.save(ignore_permissions=True)

		with self.set_user(self.admin):
			remove_team_member(self.customer, self.member)

		self.assertEqual(frappe.db.get_value("User", self.member, "enabled"), 1)

	def test_a_disabled_customer_cannot_change_its_team(self):
		"""A disabled account can still be seen but not changed."""
		frappe.db.set_value("Customer", self.customer, "disabled", 1)

		with self.set_user(self.admin):
			self.assertRaises(frappe.ValidationError, self.invite)

	def test_an_invitation_can_be_resent_until_they_sign_in(self):
		"""Resending is for people who have not signed in yet."""
		with self.set_user(self.admin):
			self.assertTrue(resend_invitation(self.customer, self.member).ok)

		frappe.db.set_value("User", self.member, "last_login", frappe.utils.now_datetime())
		with self.set_user(self.admin):
			self.assertFalse(resend_invitation(self.customer, self.member).ok)

	def test_an_account_admin_must_have_every_branch(self):
		"""The desk refuses an account admin limited to some branches."""
		doc = frappe.get_doc("Customer", self.customer)
		row = next(row for row in doc.portal_users if row.user == self.admin)
		row.branches = self.westlands

		self.assertRaises(frappe.ValidationError, doc.save, ignore_permissions=True)
