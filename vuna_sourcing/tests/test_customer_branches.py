# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate
from frappe.www.printview import validate_print_permission

from vuna_sourcing.api.portal import get_session
from vuna_sourcing.api.transactions.access import own_documents_condition, party_filters
from vuna_sourcing.api.transactions.branches import get_branches
from vuna_sourcing.api.transactions.common import all_of
from vuna_sourcing.api.transactions.credit_requests import get_creditable_invoices
from vuna_sourcing.api.transactions.customer import (
	get_account_statement,
	get_dashboard,
	get_sales_invoice,
	get_sales_invoices,
	get_sales_order,
	get_sales_orders,
)
from vuna_sourcing.api.transactions.customer_orders import get_order_form, save_order
from vuna_sourcing.api.transactions.search import search_documents
from vuna_sourcing.overrides.server.customer import search_branches
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures

SETTINGS = "Sourcing Settings"


class TestCustomerBranches(SourcingFixtures, IntegrationTestCase):
	"""Portal users limited to some of a customer's branches, run as those users."""

	price_list = "_Test Portal Branch Prices"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		if not frappe.db.exists("Price List", cls.price_list):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": cls.price_list,
					"currency": frappe.get_cached_value("Company", cls.company, "default_currency"),
					"selling": 1,
					"enabled": 1,
				}
			).insert(ignore_permissions=True)
		frappe.db.commit()

	def setUp(self):
		self.use_setting("require_branch_for_branch_customers", 1)

		self.customer, self.owner_user = self.make_customer()
		self.westlands = self.add_address("_Test Westlands")
		self.industrial = self.add_address("_Test Industrial Area")
		self.branch_user = make_test_user(["Customer"], first_name="John", last_name="Doe").name
		self.give_access(self.branch_user, [self.westlands])

		self.westlands_order = self.make_order(self.westlands)
		self.industrial_order = self.make_order(self.industrial)

	def use_setting(self, field, value):
		current = frappe.db.get_single_value(SETTINGS, field)
		self.addCleanup(frappe.db.set_single_value, SETTINGS, field, current)
		frappe.db.set_single_value(SETTINGS, field, value)

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

	def make_orderable_item(self):
		return (
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "_Test Portal Branch Item " + frappe.generate_hash(length=6),
					"item_group": self.item_group,
					"publish_on_portal": 1,
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"item_defaults": [{"company": self.company, "default_warehouse": self.warehouse}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def give_access(self, user, branches):
		doc = frappe.get_doc("Customer", self.customer)
		doc.append("portal_users", {"user": user, "branches": "\n".join(branches)})
		doc.save(ignore_permissions=True)

	def make_order(self, branch, submit=True):
		doc = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": self.customer,
				"company": self.company,
				"shipping_address_name": branch,
				"transaction_date": nowdate(),
				"delivery_date": add_days(nowdate(), 7),
				"currency": frappe.get_cached_value("Company", self.company, "default_currency"),
				"conversion_rate": 1,
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"rate": 100,
						"uom": "Nos",
						"conversion_factor": 1,
						"warehouse": self.warehouse,
						"delivery_date": add_days(nowdate(), 7),
					}
				],
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		if submit:
			doc.submit()
		return doc

	def invoice(self, order):
		doc = make_sales_invoice(order.name)
		doc.due_date = add_days(nowdate(), 30)
		doc.flags.ignore_permissions = True
		doc.insert()
		doc.submit()
		return doc

	def names(self, page):
		return {row["name"] for row in page["rows"]}

	def test_a_branch_user_sees_only_their_branch_orders(self):
		"""A user limited to one branch lists and opens only that branch's orders."""
		with self.set_user(self.branch_user):
			page = get_sales_orders()
			self.assertEqual(self.names(page), {self.westlands_order.name})
			self.assertEqual(
				page["rows"][0]["branch"], self.westlands, "rows say which branch they belong to"
			)
			self.assertEqual(get_sales_order(self.westlands_order.name)["name"], self.westlands_order.name)
			self.assertRaises(frappe.PermissionError, get_sales_order, self.industrial_order.name)

	def test_a_user_with_no_branches_picked_sees_every_branch(self):
		"""A portal user with an empty branch list is the customer's super user."""
		with self.set_user(self.owner_user):
			self.assertEqual(
				self.names(get_sales_orders()), {self.westlands_order.name, self.industrial_order.name}
			)

	def test_a_user_can_be_given_several_branches(self):
		"""Picking two branches shows the documents of both."""
		user = make_test_user(["Customer"], first_name="Jane", last_name="Doe").name
		self.give_access(user, [self.westlands, self.industrial])

		with self.set_user(user):
			self.assertEqual(
				self.names(get_sales_orders()), {self.westlands_order.name, self.industrial_order.name}
			)

	def test_a_branch_user_cannot_open_another_branchs_invoice(self):
		"""Invoices follow the order's branch, and another branch's invoice is refused."""
		mine = self.invoice(self.westlands_order)
		theirs = self.invoice(self.industrial_order)

		with self.set_user(self.branch_user):
			self.assertEqual(self.names(get_sales_invoices()), {mine.name})
			self.assertRaises(frappe.PermissionError, get_sales_invoice, theirs.name)

	def test_the_branch_filter_narrows_lists_for_a_customer_wide_user(self):
		"""A customer-wide user can filter lists to one or more branches."""
		with self.set_user(self.owner_user):
			page = get_sales_orders(customer=self.customer, branches=[self.industrial])

		self.assertEqual(self.names(page), {self.industrial_order.name})

	def test_a_branch_user_cannot_filter_by_a_branch_they_do_not_have(self):
		"""Asking for another branch through the filter is refused, not silently widened."""
		with self.set_user(self.branch_user):
			self.assertRaises(
				frappe.PermissionError,
				get_sales_orders,
				customer=self.customer,
				branches=[self.industrial],
			)

	def test_another_customers_user_cannot_use_these_branches(self):
		"""A user of another customer gets nothing for these branches."""
		_other, stranger = self.make_customer()

		with self.set_user(stranger):
			self.assertRaises(frappe.PermissionError, get_sales_order, self.westlands_order.name)
			self.assertRaises(
				frappe.PermissionError, get_sales_orders, customer=self.customer, branches=[self.westlands]
			)

	def test_printing_and_the_list_condition_follow_the_branch(self):
		"""The permission hooks give the same answer as the portal endpoints."""
		with self.set_user(self.branch_user):
			validate_print_permission(frappe.get_doc("Sales Order", self.westlands_order.name))
			self.assertRaises(
				frappe.PermissionError,
				validate_print_permission,
				frappe.get_doc("Sales Order", self.industrial_order.name),
			)
			condition = own_documents_condition(self.branch_user, "Sales Order")

		visible = frappe.get_all(
			"Sales Order",
			filters=all_of(
				party_filters("Sales Order", self.branch_user),
				{"name": ("in", [self.westlands_order.name, self.industrial_order.name])},
			),
			pluck="name",
		)
		self.assertTrue(condition, "branch users get a list condition")
		self.assertEqual(visible, [self.westlands_order.name])

	def test_staff_still_see_every_branch(self):
		"""Desk staff are not limited by portal branches."""
		staff = make_test_user(["Sales User"], first_name="Sales").name

		with self.set_user(staff):
			self.assertTrue(frappe.has_permission("Sales Order", doc=self.industrial_order.name))

	def test_pending_invoices_follow_the_branch(self):
		"""A branch user's pending invoices and balance come from their branch invoices only."""
		mine = self.invoice(self.westlands_order)
		theirs = self.invoice(self.industrial_order)

		with self.set_user(self.branch_user):
			statement = get_account_statement(self.customer, self.company).data
			balance = get_dashboard(self.customer)["balance"]

		vouchers = {row["voucher_no"] for row in statement["section"]["rows"]}
		self.assertIn(mine.name, vouchers)
		self.assertNotIn(theirs.name, vouchers)
		self.assertTrue(statement["branch_limited"])
		self.assertEqual(balance["outstanding"], statement["section"]["totals"]["outstanding"])

		with self.set_user(self.owner_user):
			everything = get_account_statement(self.customer, self.company).data

		self.assertTrue(
			{mine.name, theirs.name} <= {row["voucher_no"] for row in everything["section"]["rows"]}
		)
		self.assertFalse(everything["branch_limited"])

	def test_a_branch_user_does_not_see_payments_that_have_no_branch(self):
		"""Unallocated payments carry no branch, so they stay off a branch user's statement."""
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		self.invoice(self.westlands_order)
		advance = get_payment_entry("Sales Order", self.industrial_order.name)
		advance.reference_no = "_Test advance"
		advance.reference_date = nowdate()
		advance.paid_amount = advance.received_amount = 40
		advance.references = []
		advance.flags.ignore_permissions = True
		advance.insert()
		advance.submit()

		with self.set_user(self.branch_user):
			rows = get_account_statement(self.customer, self.company).data["section"]["rows"]
		with self.set_user(self.owner_user):
			owner_rows = get_account_statement(self.customer, self.company).data["section"]["rows"]

		self.assertNotIn(advance.name, {row["voucher_no"] for row in rows})
		self.assertIn(advance.name, {row["voucher_no"] for row in owner_rows})

	def test_pending_invoices_are_fetched_one_company_at_a_time(self):
		"""Nothing is fetched until a company is chosen when the customer deals with several."""
		self.invoice(self.westlands_order)

		with self.set_user(self.owner_user):
			statement = get_account_statement(self.customer).data
			self.assertEqual(statement["companies"], [self.company])
			self.assertEqual(statement["company"], self.company, "a single company is picked for them")
			self.assertRaises(
				frappe.ValidationError, get_account_statement, self.customer, "_Test Not Their Company"
			)

	def test_the_session_says_whether_a_user_has_every_branch(self):
		"""The session only flags branch-limited users; the branch list comes from its own endpoint."""
		with self.set_user(self.branch_user):
			branch_party = next(p for p in get_session()["parties"] if p["name"] == self.customer)
		with self.set_user(self.owner_user):
			owner_party = next(p for p in get_session()["parties"] if p["name"] == self.customer)

		self.assertFalse(branch_party["all_branches"])
		self.assertTrue(owner_party["all_branches"])
		self.assertNotIn("branches", owner_party)

	def test_each_user_gets_their_own_branch_list(self):
		"""A branch user lists their branches only; a customer-wide user lists every shipping address."""
		with self.set_user(self.branch_user):
			mine = get_branches(self.customer).data
		with self.set_user(self.owner_user):
			everything = get_branches(self.customer).data

		self.assertFalse(mine["all_branches"])
		self.assertEqual([b["name"] for b in mine["branches"]], [self.westlands])
		self.assertTrue(everything["all_branches"])
		self.assertEqual({b["name"] for b in everything["branches"]}, {self.westlands, self.industrial})

	def test_another_customers_user_cannot_list_these_branches(self):
		"""Listing branches checks the user is linked to the customer."""
		_other, stranger = self.make_customer()

		with self.set_user(stranger):
			self.assertRaises(frappe.PermissionError, get_branches, self.customer)

	def test_a_billing_address_is_not_a_branch(self):
		"""Only shipping addresses are branches, in the portal list and when assigning them on the desk."""
		billing = self.add_address("_Test Head Office", address_type="Billing")

		with self.set_user(self.owner_user):
			names = {b["name"] for b in get_branches(self.customer).data["branches"]}
		self.assertNotIn(billing, names)

		doc = frappe.get_doc("Customer", self.customer)
		doc.portal_users[-1].branches = billing
		self.assertRaises(frappe.ValidationError, doc.save, ignore_permissions=True)

	def test_the_preferred_shipping_address_counts_as_a_branch(self):
		"""An address ticked as the preferred shipping address is a branch whatever its type."""
		depot = self.add_address("_Test Depot", address_type="Office")
		frappe.db.set_value("Address", depot, "is_shipping_address", 1)

		with self.set_user(self.owner_user):
			names = {b["name"] for b in get_branches(self.customer).data["branches"]}

		self.assertIn(depot, names)

	def test_a_branch_that_stopped_being_shipping_does_not_block_saving(self):
		"""Saving the customer keeps a branch it already had, even after the address changed type."""
		frappe.db.set_value("Address", self.westlands, "address_type", "Billing")

		doc = frappe.get_doc("Customer", self.customer)
		doc.save(ignore_permissions=True)

		self.assertEqual(doc.portal_users[-1].branches, self.westlands)

	def test_the_desk_search_finds_shipping_addresses_by_text(self):
		"""Pick Branches searches on the server and returns shipping addresses only."""
		self.add_address("_Test Westlands Billing", address_type="Billing")

		found = [option["value"] for option in search_branches(self.customer, "Westlands").data]

		self.assertEqual(found, [self.westlands])

	def test_the_desk_search_keeps_the_picked_branches(self):
		"""Branches already picked keep their labels even when the search text does not match them."""
		found = search_branches(self.customer, "Industrial", [self.westlands]).data

		self.assertEqual([option["value"] for option in found], [self.westlands, self.industrial])
		self.assertTrue(found[0]["label"].startswith("_Test Westlands"))

	def test_a_portal_user_cannot_use_the_desk_search(self):
		"""The desk search needs read access to the customer, which portal users do not have."""
		with self.set_user(self.branch_user):
			self.assertRaises(frappe.PermissionError, search_branches, self.customer, "")

	def test_a_branch_user_orders_only_for_their_branches(self):
		"""The order form offers the user's branches only, and another branch is refused."""
		self.use_setting("allow_customer_sales_orders", 1)
		selling_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
		self.addCleanup(frappe.db.set_single_value, "Selling Settings", "selling_price_list", selling_list)
		frappe.db.set_single_value("Selling Settings", "selling_price_list", self.price_list)
		doc = frappe.get_doc("Customer", self.customer)
		doc.append("accounts", {"company": self.company})
		doc.save(ignore_permissions=True)
		item = self.make_orderable_item()
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": item,
				"price_list": self.price_list,
				"price_list_rate": 100,
				"customer": self.customer,
				"valid_from": add_days(nowdate(), -30),
			}
		).insert(ignore_permissions=True)
		payload = {
			"customer": self.customer,
			"company": self.company,
			"items": [{"item_code": item, "qty": 1, "uom": "Nos"}],
			"delivery_date": add_days(nowdate(), 7),
		}

		with self.set_user(self.branch_user):
			form = get_order_form(self.customer).data
			draft = save_order(**payload).data
			self.assertRaises(frappe.ValidationError, save_order, **payload, shipping_address=self.industrial)

		self.assertEqual([address["name"] for address in form["addresses"]], [self.westlands])
		self.assertEqual(draft["shipping_address"], self.westlands, "their only branch is picked for them")

	def test_a_branch_user_cannot_ask_for_credit_on_another_branchs_invoice(self):
		"""Creditable invoices are limited to the user's branches."""
		self.use_setting("allow_customer_credit_requests", 1)
		mine = self.invoice(self.westlands_order)
		self.invoice(self.industrial_order)

		with self.set_user(self.branch_user):
			rows = get_creditable_invoices(self.customer).data

		self.assertEqual([row["name"] for row in rows], [mine.name])

	def test_a_branch_must_be_one_of_the_customers_addresses(self):
		"""The desk refuses a branch that belongs to no address of this customer."""
		doc = frappe.get_doc("Customer", self.customer)
		doc.portal_users[-1].branches = "_Test Somewhere Else-Shipping"

		self.assertRaises(frappe.ValidationError, doc.save, ignore_permissions=True)

	def test_a_user_cannot_be_listed_twice_on_one_customer(self):
		"""All of a user's branches go on one row so their access is unambiguous."""
		doc = frappe.get_doc("Customer", self.customer)
		doc.append("portal_users", {"user": self.branch_user, "branches": self.industrial})

		self.assertRaises(frappe.ValidationError, doc.save, ignore_permissions=True)

	def test_a_document_without_a_branch_cannot_be_submitted_for_a_branch_customer(self):
		"""Staff must set the shipping address so the right branch can see the document."""
		draft = self.make_order(None, submit=False)

		self.assertRaises(frappe.ValidationError, draft.submit)

	def test_the_branch_requirement_can_be_turned_off(self):
		"""With the setting off, a document without a branch is visible only to customer-wide users."""
		self.use_setting("require_branch_for_branch_customers", 0)
		order = self.make_order(None)

		with self.set_user(self.owner_user):
			self.assertIn(order.name, self.names(get_sales_orders()))
		with self.set_user(self.branch_user):
			self.assertNotIn(order.name, self.names(get_sales_orders()))

	def test_search_follows_the_branch(self):
		"""A branch user's search only finds documents for their branches."""
		with self.set_user(self.branch_user):
			groups = search_documents("Customer", self.customer, self.industrial_order.name).data["groups"]
			own = search_documents("Customer", self.customer, self.westlands_order.name).data["groups"]

		self.assertEqual(groups, [])
		self.assertEqual(own[0]["results"][0]["name"], self.westlands_order.name)
