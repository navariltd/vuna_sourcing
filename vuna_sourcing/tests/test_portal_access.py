# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from vuna_sourcing.api.portal import check_party_access, get_linked_parties, get_session


class TestPortalAccess(IntegrationTestCase):
	"""Both halves of the rule: the role, and the portal_users row."""

	def make_user(self, roles=()):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"{frappe.generate_hash(length=10)}@example.com",
				"first_name": "Portal",
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)
		return user.name

	def make_supplier(self, portal_users=()):
		group = frappe.get_all("Supplier Group", filters={"is_group": 0}, limit=1, pluck="name")[0]
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": "_Test Portal Supplier " + frappe.generate_hash(length=6),
				"supplier_group": group,
				"portal_users": [{"user": u} for u in portal_users],
			}
		).insert(ignore_permissions=True)
		return supplier

	def make_customer(self, portal_users=()):
		group = frappe.get_all("Customer Group", filters={"is_group": 0}, limit=1, pluck="name")[0]
		territory = frappe.get_all("Territory", filters={"is_group": 0}, limit=1, pluck="name")[0]
		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": "_Test Portal Customer " + frappe.generate_hash(length=6),
				"customer_group": group,
				"territory": territory,
				"portal_users": [{"user": u} for u in portal_users],
			}
		).insert(ignore_permissions=True)
		return customer

	def strip_role(self, user, role):
		doc = frappe.get_doc("User", user)
		doc.roles = [r for r in doc.roles if r.role != role]
		doc.save(ignore_permissions=True)

	# ------------------------------------------------------------------
	# The two halves of the rule
	# ------------------------------------------------------------------

	def test_no_role_and_no_link_sees_nothing(self):
		user = self.make_user()
		with self.set_user(user):
			self.assertEqual(get_linked_parties(), [])

	def test_portal_row_without_the_role_grants_nothing(self):
		"""The row says which supplier; the role is what opens the door at all."""
		user = self.make_user()
		supplier = self.make_supplier(portal_users=[user])

		# ERPNext grants the role on save, so take it away to isolate the row.
		self.strip_role(user, "Supplier")
		self.assertTrue(
			frappe.db.exists("Portal User", {"user": user, "parent": supplier.name}),
			"the portal_users row should still be in place",
		)

		with self.set_user(user):
			self.assertEqual(get_linked_parties(), [])

	def test_role_without_a_portal_row_grants_no_party(self):
		user = self.make_user(["Supplier"])
		with self.set_user(user):
			self.assertEqual(get_linked_parties(), [])

			session = get_session()
			self.assertTrue(session["can_apply"])
			self.assertTrue(session["is_applicant"], "role but no party means an applicant")

	def test_role_and_portal_row_grants_the_party(self):
		user = self.make_user()
		supplier = self.make_supplier(portal_users=[user])

		with self.set_user(user):
			parties = get_linked_parties()

		self.assertEqual(len(parties), 1)
		self.assertEqual(parties[0]["name"], supplier.name)
		self.assertEqual(parties[0]["party_type"], "Supplier")
		self.assertEqual(parties[0]["title"], supplier.supplier_name)

	# ------------------------------------------------------------------
	# One login, several parties
	# ------------------------------------------------------------------

	def test_user_linked_to_two_suppliers_sees_both(self):
		user = self.make_user()
		first = self.make_supplier(portal_users=[user])
		second = self.make_supplier(portal_users=[user])

		with self.set_user(user):
			names = {p["name"] for p in get_linked_parties()}

		self.assertEqual(names, {first.name, second.name})

	def test_user_linked_to_a_supplier_and_a_customer_sees_both_types(self):
		user = self.make_user()
		supplier = self.make_supplier(portal_users=[user])
		customer = self.make_customer(portal_users=[user])

		with self.set_user(user):
			parties = get_linked_parties()

		by_type = {p["party_type"]: p["name"] for p in parties}
		self.assertEqual(by_type, {"Supplier": supplier.name, "Customer": customer.name})

	def test_customer_role_alone_does_not_expose_suppliers(self):
		user = self.make_user()
		supplier = self.make_supplier(portal_users=[user])
		customer = self.make_customer(portal_users=[user])

		self.strip_role(user, "Supplier")

		with self.set_user(user):
			parties = get_linked_parties()

		self.assertEqual([p["name"] for p in parties], [customer.name])
		self.assertNotIn(supplier.name, [p["name"] for p in parties])

	# ------------------------------------------------------------------
	# Acting for a party
	# ------------------------------------------------------------------

	def test_check_party_access_allows_a_linked_party(self):
		user = self.make_user()
		supplier = self.make_supplier(portal_users=[user])

		with self.set_user(user):
			check_party_access("Supplier", supplier.name)

	def test_check_party_access_refuses_someone_elses_party(self):
		user = self.make_user(["Supplier"])
		other = self.make_supplier()

		with self.set_user(user):
			self.assertRaises(frappe.PermissionError, check_party_access, "Supplier", other.name)

	def test_check_party_access_refuses_an_unknown_party_type(self):
		user = self.make_user(["Supplier"])
		with self.set_user(user):
			self.assertRaises(frappe.PermissionError, check_party_access, "Employee", "anything")

	def test_guest_is_refused(self):
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, get_session)
