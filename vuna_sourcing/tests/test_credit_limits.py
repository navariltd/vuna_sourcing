# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from vuna_sourcing.api.portal import get_session
from vuna_sourcing.api.transactions.credit_limits import get_credit_status
from vuna_sourcing.api.transactions.customer_orders import submit_order
from vuna_sourcing.tests.test_customer_orders import CustomerOrderFixtures


class TestCreditLimits(CustomerOrderFixtures, IntegrationTestCase):
	"""Customers seeing their credit limit and balance on the portal."""

	def setUp(self):
		super().setUp()
		current = frappe.db.get_single_value("Sourcing Settings", "show_customer_credit_limits")
		self.addCleanup(
			frappe.db.set_single_value, "Sourcing Settings", "show_customer_credit_limits", current
		)
		frappe.db.set_single_value("Sourcing Settings", "show_customer_credit_limits", 1)

	def set_credit_limit(self, limit, bypass=1):
		doc = frappe.get_doc("Customer", self.customer)
		doc.set(
			"credit_limits",
			[{"company": self.company, "credit_limit": limit, "bypass_credit_limit_check": bypass}],
		)
		doc.save(ignore_permissions=True)

	def confirmed_order(self, qty):
		draft = self.order(qty=qty)
		with self.set_user(self.user):
			submit_order(
				customer=self.customer,
				name=draft["name"],
				items=[{"item_code": self.item_code, "qty": qty}],
				delivery_date=add_days(nowdate(), 7),
			)
		doc = frappe.get_doc("Sales Order", draft["name"])
		doc.flags.ignore_permissions = True
		doc.submit()
		return doc

	def status(self, customer=None, user=None):
		with self.set_user(user or self.user):
			return get_credit_status(customer or self.customer).data

	def ours(self, status):
		return next(row for row in status["rows"] if row["company"] == self.company)

	def test_the_customer_sees_how_far_over_the_limit_they_are(self):
		"""A confirmed order above the limit shows the overrun and leaves nothing available."""
		self.set_credit_limit(200)
		self.confirmed_order(qty=3)

		row = self.ours(self.status())

		self.assertEqual(row["credit_limit"], 200)
		self.assertEqual(row["used"], 300)
		self.assertEqual(row["over_by"], 100)
		self.assertEqual(row["available"], 0)
		self.assertEqual(row["state"], "over")
		self.assertEqual(row["not_yet_invoiced"], 300)
		self.assertIn(self.company, self.status()["over_limit"])

	def test_room_left_and_near_limit_are_reported(self):
		"""Using 90% or more of the limit is flagged as near, with the room left."""
		self.set_credit_limit(1000)
		self.confirmed_order(qty=9)

		row = self.ours(self.status())

		self.assertEqual(row["available"], 100)
		self.assertEqual(row["over_by"], 0)
		self.assertEqual(row["state"], "near")

	def test_a_company_without_a_limit_is_left_out(self):
		"""No limit on the customer, its group or the company means nothing to show."""
		if frappe.get_cached_value("Company", self.company, "credit_limit"):
			self.skipTest("The test company has its own credit limit.")

		self.assertEqual([row for row in self.status()["rows"] if row["company"] == self.company], [])

	def test_an_order_over_the_limit_is_still_sent_from_the_portal(self):
		"""The portal never blocks an order; the desk submit applies the credit check."""
		self.set_credit_limit(100, bypass=0)
		draft = self.order(qty=5)

		with self.set_user(self.user):
			sent = submit_order(
				customer=self.customer,
				name=draft["name"],
				items=[{"item_code": self.item_code, "qty": 5}],
			)
		self.assertTrue(sent.ok)

	def test_another_customers_credit_is_not_visible(self):
		"""A user of another customer cannot read this customer's credit."""
		self.set_credit_limit(200)
		_other, other_user = self.make_ordering_customer()

		self.assertRaises(frappe.PermissionError, self.status, user=other_user)

	def test_credit_is_hidden_when_the_setting_is_off(self):
		"""With the setting off the endpoint refuses and the session hides the feature."""
		frappe.db.set_single_value("Sourcing Settings", "show_customer_credit_limits", 0)

		self.assertRaises(frappe.PermissionError, self.status)
		with self.set_user(self.user):
			self.assertFalse(get_session()["features"]["credit_limits"])

	def test_a_user_limited_to_some_branches_cannot_see_account_credit(self):
		"""Account-wide balances stay hidden from users limited to some branches."""
		self.set_credit_limit(200)
		branch = self.add_address(self.customer, "_Test Credit Branch " + frappe.generate_hash(length=4))
		doc = frappe.get_doc("Customer", self.customer)
		doc.portal_users[0].branches = branch
		doc.save(ignore_permissions=True)
		frappe.clear_cache()

		self.assertRaises(frappe.PermissionError, self.status)
