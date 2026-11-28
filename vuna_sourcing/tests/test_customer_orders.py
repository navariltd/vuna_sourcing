# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import io

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate
from pypdf import PdfWriter

from vuna_sourcing.api.transactions.customer import get_sales_order, get_sales_orders
from vuna_sourcing.api.transactions.customer_orders import (
	attach_po_document,
	clear_order,
	delete_order,
	get_order_categories,
	get_order_form,
	get_orderable_items,
	price_order,
	save_order,
	submit_order,
	withdraw_order,
)
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures
from vuna_sourcing.vuna_sourcing.doctype.sourcing_order_field.sourcing_order_field import (
	get_sales_order_fields,
)


def blank_pdf() -> bytes:
	writer = PdfWriter()
	writer.add_blank_page(width=72, height=72)
	buffer = io.BytesIO()
	writer.write(buffer)
	return buffer.getvalue()


def restrict_to(doc, companies):
	doc.restrict_to_companies = 1
	doc.set("allowed_companies", [{"company": company} for company in companies])
	doc.save(ignore_permissions=True)


class CustomerOrderFixtures(SourcingFixtures):
	price_list = "_Test Portal Order Prices"
	other_company = "_Test Portal Order Company"

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

		if not frappe.db.exists("Company", cls.other_company):
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": cls.other_company,
					"abbr": "_TPOC",
					"default_currency": frappe.get_cached_value("Company", cls.company, "default_currency"),
					"country": frappe.get_cached_value("Company", cls.company, "country"),
					"create_chart_of_accounts_based_on": "Standard Template",
					"chart_of_accounts": "Standard",
				}
			).insert(ignore_permissions=True)
		frappe.db.commit()

	_order_fields_saved = False

	def setUp(self):
		current = frappe.db.get_single_value("Sourcing Settings", "allow_customer_sales_orders")
		self.addCleanup(
			frappe.db.set_single_value, "Sourcing Settings", "allow_customer_sales_orders", current
		)
		frappe.db.set_single_value("Sourcing Settings", "allow_customer_sales_orders", 1)
		self.use_default_company(None)
		selling_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
		self.addCleanup(frappe.db.set_single_value, "Selling Settings", "selling_price_list", selling_list)
		frappe.db.set_single_value("Selling Settings", "selling_price_list", self.price_list)
		self.use_order_fields()

		self.customer, self.user = self.make_ordering_customer()
		self.item_code = self.make_item()
		self.add_price(self.item_code, 100)

	def use_default_company(self, company):
		current = frappe.db.get_single_value("Sourcing Settings", "default_ordering_company")
		self.addCleanup(frappe.db.set_single_value, "Sourcing Settings", "default_ordering_company", current)
		frappe.db.set_single_value("Sourcing Settings", "default_ordering_company", company)

	def use_order_fields(self, *rows):
		settings = frappe.get_single("Sourcing Settings")
		if not self._order_fields_saved:
			previous = [row.as_dict() for row in settings.portal_order_fields]
			self.addCleanup(self.restore_order_fields, previous)
			self._order_fields_saved = True
		settings.set("portal_order_fields", list(rows))
		settings.save()
		return settings

	def restore_order_fields(self, previous):
		self._order_fields_saved = False
		settings = frappe.get_single("Sourcing Settings")
		settings.set("portal_order_fields", previous)
		settings.save()

	def make_ordering_customer(self, companies=None):
		customer, user = self.make_customer()
		restrict_to(frappe.get_doc("Customer", customer), companies or [self.company])
		return customer, user

	def make_item(self, company=None, **fields):
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "_Test Portal Order Item " + frappe.generate_hash(length=6),
				"item_group": self.item_group,
				"publish_on_portal": 1,
				"stock_uom": "Nos",
				"is_stock_item": 0,
				**fields,
			}
		).insert(ignore_permissions=True)
		if company:
			restrict_to(item, [company])
		return item.name

	def add_price(self, item_code, rate, customer=None, valid_from=None):
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": item_code,
				"price_list": self.price_list,
				"price_list_rate": rate,
				"customer": customer,
				"valid_from": valid_from or add_days(nowdate(), -30),
			}
		).insert(ignore_permissions=True)

	def add_address(self, customer, title, address_type="Shipping"):
		return (
			frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": title,
					"address_type": address_type,
					"address_line1": f"{title} Road",
					"city": "Nairobi",
					"country": frappe.get_all("Country", limit=1, pluck="name")[0],
					"links": [{"link_doctype": "Customer", "link_name": customer}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def order(self, qty=2, **extra):
		payload = {
			"customer": self.customer,
			"company": self.company,
			"items": [{"item_code": self.item_code, "qty": qty, "uom": "Nos"}],
			"delivery_date": add_days(nowdate(), 7),
			**extra,
		}
		with self.set_user(self.user):
			return save_order(**payload).data


class TestCustomerOrders(CustomerOrderFixtures, IntegrationTestCase):
	"""Customers placing Sales Orders from the portal, run as the customer."""

	def test_an_order_is_saved_as_a_hidden_portal_draft(self):
		draft = self.order(qty=3)
		doc = frappe.get_doc("Sales Order", draft["name"])

		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(doc.created_from_portal, 1)
		self.assertEqual(doc.portal_submission_status, "Pending")
		self.assertEqual(doc.company, self.company)
		self.assertEqual(draft["grand_total"], 300)

	def test_ordering_is_refused_when_the_setting_is_off(self):
		frappe.db.set_single_value("Sourcing Settings", "allow_customer_sales_orders", 0)

		self.assertRaises(frappe.PermissionError, self.order)
		with self.set_user(self.user):
			self.assertFalse(get_order_form(self.customer).ok)
			self.assertFalse(get_sales_orders(customer=self.customer)["can_order"])

	def test_the_customers_own_price_wins_over_a_newer_general_price(self):
		self.add_price(self.item_code, 80, customer=self.customer, valid_from=add_days(nowdate(), -20))
		self.add_price(self.item_code, 120, valid_from=add_days(nowdate(), -1))

		draft = self.order(qty=1)

		self.assertEqual(draft["items"][0]["rate"], 80)
		with self.set_user(self.user):
			listed = get_orderable_items(self.customer, self.company, search=self.item_code).data["rows"]
		self.assertEqual(listed[0]["rate"], 80)

	def test_prices_come_from_the_default_selling_list_not_the_customers_own_list(self):
		"""The customer's default price list is ignored; the Selling Settings list prices the order."""
		own_list = "_Test Portal Customer Retail"
		if not frappe.db.exists("Price List", own_list):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": own_list,
					"currency": frappe.get_cached_value("Company", self.company, "default_currency"),
					"selling": 1,
					"enabled": 1,
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Customer", self.customer, "default_price_list", own_list)
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": self.item_code,
				"price_list": own_list,
				"price_list_rate": 5,
			}
		).insert(ignore_permissions=True)
		retail_only = self.make_item()
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": retail_only,
				"price_list": own_list,
				"price_list_rate": 5,
			}
		).insert(ignore_permissions=True)

		self.assertEqual(self.order(qty=1)["items"][0]["rate"], 100)
		with self.set_user(self.user):
			listed = get_orderable_items(self.customer, self.company, search=retail_only).data["rows"]
		self.assertEqual(listed, [])

	def test_another_customers_price_is_never_used(self):
		other, _user = self.make_ordering_customer()
		self.add_price(self.item_code, 10, customer=other)

		self.assertEqual(self.order(qty=1)["items"][0]["rate"], 100)

	def test_a_rate_sent_by_the_client_is_ignored(self):
		with self.set_user(self.user):
			draft = save_order(
				customer=self.customer,
				company=self.company,
				items=[
					{"item_code": self.item_code, "qty": 1, "uom": "Nos", "rate": 1, "price_list_rate": 1}
				],
				delivery_date=add_days(nowdate(), 7),
			).data

		self.assertEqual(frappe.db.get_value("Sales Order Item", {"parent": draft["name"]}, "rate"), 100)

	def test_an_item_without_a_price_is_not_offered_and_cannot_be_ordered(self):
		self.item_code = self.make_item()

		with self.set_user(self.user):
			listed = get_orderable_items(self.customer, self.company, search=self.item_code).data["rows"]
		self.assertEqual(listed, [])
		self.assertRaisesRegex(frappe.ValidationError, "do not have a price", self.order)

	def test_only_sales_items_of_the_ordering_company_can_be_ordered(self):
		other_company = self.other_company
		elsewhere = self.make_item(company=other_company)
		not_for_sale = self.make_item(is_sales_item=0)
		self.add_price(elsewhere, 50)
		self.add_price(not_for_sale, 50)

		with self.set_user(self.user):
			listed = {
				row["item_code"]
				for code in (self.item_code, elsewhere, not_for_sale)
				for row in get_orderable_items(self.customer, self.company, search=code).data["rows"]
			}
		self.assertIn(self.item_code, listed)
		self.assertNotIn(elsewhere, listed)
		self.assertNotIn(not_for_sale, listed)

		for item_code in (elsewhere, not_for_sale):
			self.item_code = item_code
			self.assertRaisesRegex(frappe.ValidationError, "cannot be ordered", self.order)

	def test_a_customer_orders_only_from_their_allowed_companies(self):
		"""A customer restricted to some companies cannot order from any other company."""
		self.assertRaises(frappe.ValidationError, self.order, company=self.other_company)

		customer, user = self.make_ordering_customer([self.other_company])
		with self.set_user(user):
			form = get_order_form(customer).data
			self.assertTrue(get_sales_orders(customer=customer)["can_order"])
			self.assertRaisesRegex(
				frappe.ValidationError,
				"company you can order from",
				save_order,
				customer=customer,
				company=self.company,
				items=[{"item_code": self.item_code, "qty": 1}],
			)

		self.assertEqual(form["companies"], [self.other_company])

	def test_an_unrestricted_customer_cannot_order_without_a_default_ordering_company(self):
		"""Without Restrict to Companies or a default ordering company, a customer sees no company and cannot order."""
		self.use_default_company(None)
		customer, user = self.make_customer()

		with self.set_user(user):
			form = get_order_form(customer)
			self.assertFalse(get_sales_orders(customer=customer)["can_order"])
			for company in (None, self.company, self.other_company):
				self.assertRaisesRegex(
					frappe.ValidationError,
					"not set up for ordering",
					save_order,
					customer=customer,
					company=company,
					items=[{"item_code": self.item_code, "qty": 1}],
				)

		self.assertFalse(form.ok)
		self.assertIsNone(form.data)

	def test_an_unrestricted_customer_orders_only_from_the_default_ordering_company(self):
		"""A customer without Restrict to Companies sees and orders from the default ordering company only."""
		self.use_default_company(self.company)
		customer, user = self.make_customer()

		with self.set_user(user):
			form = get_order_form(customer).data
			draft = save_order(
				customer=customer,
				items=[{"item_code": self.item_code, "qty": 1}],
				delivery_date=add_days(nowdate(), 7),
			).data
			self.assertRaisesRegex(
				frappe.ValidationError,
				"company you can order from",
				save_order,
				customer=customer,
				company=self.other_company,
				items=[{"item_code": self.item_code, "qty": 1}],
			)
			self.assertRaisesRegex(
				frappe.ValidationError,
				"company you can order from",
				get_orderable_items,
				customer,
				self.other_company,
			)

		self.assertEqual(form["companies"], [self.company])
		self.assertEqual(draft["company"], self.company)

	def test_restricted_companies_on_the_customer_win_over_the_default_ordering_company(self):
		"""A customer's Allowed Companies replace the default ordering company, not add to it."""
		self.use_default_company(self.company)
		customer, user = self.make_ordering_customer([self.other_company])

		with self.set_user(user):
			form = get_order_form(customer).data
			self.assertRaisesRegex(
				frappe.ValidationError,
				"company you can order from",
				save_order,
				customer=customer,
				company=self.company,
				items=[{"item_code": self.item_code, "qty": 1}],
			)

		self.assertEqual(form["companies"], [self.other_company])

	def test_a_restricted_customer_without_allowed_companies_cannot_order(self):
		"""Restrict to Companies with no Allowed Companies blocks ordering, even with a default ordering company."""
		self.use_default_company(self.company)
		customer, user = self.make_customer()
		frappe.db.set_value("Customer", customer, "restrict_to_companies", 1)

		with self.set_user(user):
			self.assertFalse(get_order_form(customer).ok)
			self.assertRaisesRegex(
				frappe.ValidationError,
				"not set up for ordering",
				save_order,
				customer=customer,
				company=self.company,
				items=[{"item_code": self.item_code, "qty": 1}],
			)

	def test_a_draft_cannot_be_sent_once_its_company_is_no_longer_allowed(self):
		"""Taking a company off a customer's Allowed Companies stops their drafts for it being saved or sent."""
		with self.set_user(self.user):
			draft = save_order(
				customer=self.customer,
				items=[{"item_code": self.item_code, "qty": 1}],
				delivery_date=add_days(nowdate(), 7),
			).data

		restrict_to(frappe.get_doc("Customer", self.customer), [self.other_company])

		with self.set_user(self.user):
			for action in (save_order, submit_order):
				self.assertRaisesRegex(
					frappe.ValidationError,
					"company you can order from",
					action,
					customer=self.customer,
					name=draft["name"],
					items=[{"item_code": self.item_code, "qty": 1}],
					delivery_date=add_days(nowdate(), 7),
				)

		self.assertEqual(frappe.db.get_value("Sales Order", draft["name"], "docstatus"), 0)

	def test_another_customers_user_cannot_read_the_ordering_companies(self):
		"""A portal user cannot see which companies another customer may order from."""
		_other, intruder = self.make_ordering_customer([self.other_company])

		with self.set_user(intruder):
			self.assertRaises(frappe.PermissionError, get_order_form, self.customer)
			self.assertRaises(frappe.PermissionError, get_orderable_items, self.customer, self.company)

	def test_items_restricted_to_another_company_are_hidden_and_refused_for_the_default_company(self):
		"""Items limited to other companies cannot be browsed, priced or ordered through the default ordering company."""
		self.use_default_company(self.company)
		customer, user = self.make_customer()
		elsewhere = self.make_item(company=self.other_company)
		here = self.make_item(company=self.company)
		for item_code in (elsewhere, here):
			self.add_price(item_code, 50)

		with self.set_user(user):
			listed = {
				row["item_code"]
				for code in (self.item_code, elsewhere, here)
				for row in get_orderable_items(customer, search=code).data["rows"]
			}
			counted = get_order_categories(customer).data["all_items"]
			for action in (price_order, save_order, submit_order):
				self.assertRaisesRegex(
					frappe.ValidationError,
					"cannot be ordered",
					action,
					customer=customer,
					items=[{"item_code": elsewhere, "qty": 1}],
					delivery_date=add_days(nowdate(), 7),
				)
			priced = price_order(customer=customer, items=[{"item_code": here, "qty": 1}]).data

		self.assertEqual(listed, {self.item_code, here})
		self.assertNotIn(elsewhere, {row["item_code"] for row in priced["items"]})
		self.assertGreaterEqual(counted, 2)
		self.assertFalse(frappe.db.exists("Sales Order Item", {"item_code": elsewhere}))

	def test_items_are_offered_only_for_the_customers_allowed_companies(self):
		"""A restricted customer sees an item only under a company both the customer and the item allow."""
		elsewhere = self.make_item(company=self.other_company)
		self.add_price(elsewhere, 50)
		customer, user = self.make_ordering_customer([self.company, self.other_company])

		with self.set_user(user):
			here = {
				row["item_code"]
				for row in get_orderable_items(customer, self.company, search=elsewhere).data["rows"]
			}
			there = {
				row["item_code"]
				for row in get_orderable_items(customer, self.other_company, search=elsewhere).data["rows"]
			}
			draft = save_order(
				customer=customer,
				company=self.other_company,
				items=[{"item_code": elsewhere, "qty": 1}],
				delivery_date=add_days(nowdate(), 7),
			).data
			self.assertRaisesRegex(
				frappe.ValidationError,
				"cannot be ordered",
				save_order,
				customer=customer,
				company=self.company,
				items=[{"item_code": elsewhere, "qty": 1}],
			)

		self.assertEqual(here, set())
		self.assertEqual(there, {elsewhere})
		self.assertEqual(draft["company"], self.other_company)

	def test_the_only_configured_company_is_used_without_asking(self):
		with self.set_user(self.user):
			form = get_order_form(self.customer).data
			draft = save_order(
				customer=self.customer,
				items=[{"item_code": self.item_code, "qty": 1}],
				delivery_date=add_days(nowdate(), 7),
			).data

		self.assertEqual(form["companies"], [self.company])
		self.assertEqual(draft["company"], self.company)

	def test_a_customer_with_several_addresses_must_choose_one_of_their_own(self):
		first = self.add_address(self.customer, "Warehouse A " + frappe.generate_hash(length=4))
		self.add_address(self.customer, "Warehouse B " + frappe.generate_hash(length=4))
		other, _user = self.make_ordering_customer()
		foreign = self.add_address(other, "Elsewhere " + frappe.generate_hash(length=4))

		self.assertRaisesRegex(frappe.ValidationError, "deliver this order", self.order)
		self.assertRaisesRegex(
			frappe.ValidationError, "deliver this order", self.order, shipping_address=foreign
		)

		draft = self.order(shipping_address=first)
		self.assertEqual(draft["shipping_address"], first)

	def test_only_delivery_addresses_are_offered_and_accepted(self):
		"""A billing address is neither listed in the cart nor accepted as where to deliver."""
		depot = self.add_address(self.customer, "Depot " + frappe.generate_hash(length=4))
		other_depot = self.add_address(self.customer, "Depot " + frappe.generate_hash(length=4))
		billing = self.add_address(
			self.customer, "Head Office " + frappe.generate_hash(length=4), address_type="Billing"
		)

		with self.set_user(self.user):
			offered = {row["name"] for row in get_order_form(self.customer).data["addresses"]}

		self.assertEqual(offered, {depot, other_depot})
		self.assertRaisesRegex(
			frappe.ValidationError, "deliver this order", self.order, shipping_address=billing
		)

	def test_a_billing_address_is_not_picked_for_delivery_on_its_own(self):
		"""With only a billing address on file, the order is left for our team to confirm where to deliver."""
		self.add_address(
			self.customer, "Head Office " + frappe.generate_hash(length=4), address_type="Billing"
		)

		self.assertIsNone(self.order()["shipping_address"])

	def test_a_single_address_is_used_without_asking(self):
		only = self.add_address(self.customer, "Only Depot " + frappe.generate_hash(length=4))

		self.assertEqual(self.order()["shipping_address"], only)

	def test_a_pending_draft_is_hidden_from_the_desk_until_it_is_submitted(self):
		staff = make_test_user(["Sales User"], first_name="Sales").name
		draft = self.order()

		with self.set_user(staff):
			self.assertEqual(
				frappe.get_list("Sales Order", filters={"name": draft["name"]}, pluck="name"), []
			)
			self.assertFalse(frappe.has_permission("Sales Order", doc=draft["name"]))

		with self.set_user(self.user):
			submit_order(
				customer=self.customer,
				name=draft["name"],
				items=[{"item_code": self.item_code, "qty": 2, "uom": "Nos"}],
				delivery_date=add_days(nowdate(), 7),
			)

		with self.set_user(staff):
			self.assertEqual(
				frappe.get_list("Sales Order", filters={"name": draft["name"]}, pluck="name"), [draft["name"]]
			)
			self.assertTrue(frappe.has_permission("Sales Order", doc=draft["name"]))

	def test_a_desk_order_stays_visible_on_the_desk(self):
		staff = make_test_user(["Sales User"], first_name="Sales").name
		doc = frappe.new_doc("Sales Order")
		doc.flags.ignore_mandatory = True
		doc.update(
			{
				"customer": self.customer,
				"company": self.company,
				"delivery_date": add_days(nowdate(), 7),
				"items": [
					{
						"item_code": self.item_code,
						"qty": 1,
						"rate": 100,
						"delivery_date": add_days(nowdate(), 7),
					}
				],
			}
		).insert(ignore_permissions=True)

		with self.set_user(staff):
			self.assertEqual(
				frappe.get_list("Sales Order", filters={"name": doc.name}, pluck="name"), [doc.name]
			)

	def test_a_sent_order_cannot_be_changed_or_sent_twice(self):
		draft = self.order()
		payload = {
			"customer": self.customer,
			"name": draft["name"],
			"items": [{"item_code": self.item_code, "qty": 5, "uom": "Nos"}],
			"delivery_date": add_days(nowdate(), 7),
		}

		with self.set_user(self.user):
			sent = submit_order(**payload)
			self.assertEqual(sent.data["status"], "Submitted")
			self.assertRaisesRegex(
				frappe.ValidationError, "can no longer be changed", submit_order, **payload
			)
			self.assertRaisesRegex(frappe.ValidationError, "can no longer be changed", save_order, **payload)
			self.assertRaises(frappe.ValidationError, delete_order, self.customer, draft["name"])

		self.assertEqual(frappe.db.get_value("Sales Order Item", {"parent": draft["name"]}, "qty"), 5)

	def test_another_customer_cannot_touch_the_draft(self):
		draft = self.order()
		other, other_user = self.make_ordering_customer()

		with self.set_user(other_user):
			self.assertRaises(frappe.PermissionError, delete_order, other, draft["name"])
			self.assertRaises(frappe.PermissionError, delete_order, self.customer, draft["name"])
			self.assertRaises(frappe.PermissionError, get_sales_order, draft["name"])
			self.assertRaises(
				frappe.PermissionError,
				save_order,
				customer=other,
				name=draft["name"],
				items=[{"item_code": self.item_code, "qty": 1}],
				delivery_date=add_days(nowdate(), 7),
			)

	def test_the_customer_sees_their_drafts_and_sent_orders(self):
		draft = self.order()
		sent = self.order()
		with self.set_user(self.user):
			submit_order(
				customer=self.customer,
				name=sent["name"],
				items=[{"item_code": self.item_code, "qty": 1}],
				delivery_date=add_days(nowdate(), 7),
			)
			rows = {row["name"]: row["status"] for row in get_sales_orders(customer=self.customer)["rows"]}
			detail = get_sales_order(draft["name"], self.customer)

		self.assertEqual(rows, {draft["name"]: "Draft", sent["name"]: "Awaiting Confirmation"})
		self.assertTrue(detail["editable"])

	def test_a_draft_can_be_deleted(self):
		draft = self.order()

		with self.set_user(self.user):
			delete_order(self.customer, draft["name"])

		self.assertFalse(frappe.db.exists("Sales Order", draft["name"]))

	def test_a_desk_only_mandatory_field_does_not_block_the_portal_but_blocks_desk_submit(self):
		frappe.make_property_setter(
			{
				"doctype": "Sales Order",
				"fieldname": "po_date",
				"property": "reqd",
				"value": "1",
				"property_type": "Check",
			}
		)
		self.addCleanup(frappe.clear_cache, doctype="Sales Order")
		self.addCleanup(
			frappe.db.delete,
			"Property Setter",
			{"doc_type": "Sales Order", "field_name": "po_date", "property": "reqd"},
		)

		draft = self.order()
		with self.set_user(self.user):
			submit_order(
				customer=self.customer,
				name=draft["name"],
				items=[{"item_code": self.item_code, "qty": 1}],
				delivery_date=add_days(nowdate(), 7),
			)

		doc = frappe.get_doc("Sales Order", draft["name"])
		doc.flags.ignore_permissions = True
		self.assertRaises(frappe.MandatoryError, doc.submit)

	def test_a_missing_standard_field_stops_the_order_before_it_is_saved(self):
		"""Required ERPNext fields are checked before the save, so nothing is written when one is empty."""
		from vuna_sourcing.api.transactions.customer_orders import ORDER_PENDING, write_order

		doc = frappe.new_doc("Sales Order")
		doc.update({"company": self.company, "transaction_date": nowdate()})
		doc.append("items", {"item_code": self.item_code, "qty": 1})
		before = frappe.db.count("Sales Order")

		self.assertRaisesRegex(frappe.MandatoryError, "Customer", write_order, doc, ORDER_PENDING)
		self.assertTrue(doc.is_new())
		self.assertEqual(frappe.db.count("Sales Order"), before)

	def test_a_past_delivery_date_or_bad_quantity_is_refused(self):
		self.assertRaisesRegex(
			frappe.ValidationError, "cannot be in the past", self.order, delivery_date=add_days(nowdate(), -1)
		)
		self.assertRaisesRegex(frappe.ValidationError, "above zero", self.order, qty=0)
		self.assertRaisesRegex(frappe.ValidationError, "above zero", self.order, qty="inf")

	def test_a_po_number_cannot_be_reused_by_the_same_customer(self):
		first = self.order(po_no="PO-REUSE-1")

		self.assertRaisesRegex(
			frappe.ValidationError, "already used PO number", self.order, po_no="PO-REUSE-1"
		)
		with self.set_user(self.user):
			resaved = save_order(
				customer=self.customer,
				name=first["name"],
				items=[{"item_code": self.item_code, "qty": 1}],
				delivery_date=add_days(nowdate(), 7),
				po_no="PO-REUSE-1",
			).data
		self.assertEqual(resaved["po_no"], "PO-REUSE-1")

	def test_a_larger_unit_is_priced_from_its_own_price_or_the_stock_unit_price(self):
		if not frappe.db.exists("UOM", "_Test Portal Box"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "_Test Portal Box"}).insert(ignore_permissions=True)
		self.item_code = self.make_item(uoms=[{"uom": "_Test Portal Box", "conversion_factor": 12}])
		self.add_price(self.item_code, 100)

		self.assertEqual(
			self.order(qty=1, items=[{"item_code": self.item_code, "qty": 1, "uom": "_Test Portal Box"}])[
				"items"
			][0]["rate"],
			1200,
		)

		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": self.item_code,
				"price_list": self.price_list,
				"price_list_rate": 1000,
				"uom": "_Test Portal Box",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(
			self.order(qty=1, items=[{"item_code": self.item_code, "qty": 1, "uom": "_Test Portal Box"}])[
				"items"
			][0]["rate"],
			1000,
		)
		self.assertRaisesRegex(
			frappe.ValidationError,
			"cannot be ordered in",
			self.order,
			items=[{"item_code": self.item_code, "qty": 1, "uom": "Kg"}],
		)

	def test_a_sent_order_can_be_withdrawn_back_to_a_hidden_draft(self):
		staff = make_test_user(["Sales User"], first_name="Sales").name
		draft = self.order()
		payload = {
			"customer": self.customer,
			"name": draft["name"],
			"items": [{"item_code": self.item_code, "qty": 2, "uom": "Nos"}],
			"delivery_date": add_days(nowdate(), 7),
		}

		with self.set_user(self.user):
			self.assertRaisesRegex(
				frappe.ValidationError, "not been sent", withdraw_order, self.customer, draft["name"]
			)
			submit_order(**payload)
			self.assertTrue(get_sales_order(draft["name"], self.customer)["withdrawable"])
			withdraw_order(self.customer, draft["name"])
			self.assertTrue(get_sales_order(draft["name"], self.customer)["editable"])
			save_order(**{**payload, "items": [{"item_code": self.item_code, "qty": 4, "uom": "Nos"}]})

		self.assertEqual(
			frappe.db.get_value("Sales Order", draft["name"], "portal_submission_status"), "Pending"
		)
		self.assertEqual(frappe.db.get_value("Sales Order Item", {"parent": draft["name"]}, "qty"), 4)
		with self.set_user(staff):
			self.assertFalse(frappe.has_permission("Sales Order", doc=draft["name"]))

	def test_a_confirmed_order_cannot_be_withdrawn(self):
		draft = self.order()
		with self.set_user(self.user):
			submit_order(
				customer=self.customer,
				name=draft["name"],
				items=[{"item_code": self.item_code, "qty": 1}],
				delivery_date=add_days(nowdate(), 7),
			)

		doc = frappe.get_doc("Sales Order", draft["name"])
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.submit()

		with self.set_user(self.user):
			self.assertRaisesRegex(
				frappe.ValidationError, "confirmed", withdraw_order, self.customer, draft["name"]
			)

		other, other_user = self.make_ordering_customer()
		with self.set_user(other_user):
			self.assertRaises(frappe.PermissionError, withdraw_order, other, draft["name"])

	def test_prices_are_shown_and_ordered_in_the_customers_billing_currency(self):
		company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		billing = "EUR" if company_currency == "USD" else "USD"
		for from_currency, to_currency, rate in (
			(company_currency, billing, 0.01),
			(billing, company_currency, 100),
		):
			frappe.get_doc(
				{
					"doctype": "Currency Exchange",
					"date": nowdate(),
					"from_currency": from_currency,
					"to_currency": to_currency,
					"exchange_rate": rate,
					"for_selling": 1,
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Customer", self.customer, "default_currency", billing)

		with self.set_user(self.user):
			listed = get_orderable_items(self.customer, self.company, search=self.item_code).data
		draft = self.order(qty=3)

		self.assertEqual(listed["currency"], billing)
		self.assertEqual(listed["rows"][0]["rate"], 1)
		self.assertEqual(draft["currency"], billing)
		self.assertEqual(draft["items"][0]["rate"], 1)
		self.assertEqual(draft["grand_total"], 3)

	def test_a_billing_currency_without_an_exchange_rate_is_refused(self):
		current = frappe.db.get_single_value("Currency Exchange Settings", "disabled")
		self.addCleanup(frappe.db.set_single_value, "Currency Exchange Settings", "disabled", current)
		frappe.db.set_single_value("Currency Exchange Settings", "disabled", 1)
		frappe.db.set_value("Customer", self.customer, "default_currency", "_TC")
		if not frappe.db.exists("Currency", "_TC"):
			frappe.get_doc({"doctype": "Currency", "currency_name": "_TC", "enabled": 1}).insert(
				ignore_permissions=True
			)

		self.assertRaisesRegex(frappe.ValidationError, "cannot show prices in _TC", self.order)

	def test_a_desk_order_leaves_the_portal_status_blank(self):
		doc = frappe.new_doc("Sales Order")

		self.assertFalse(doc.portal_submission_status)
		self.assertFalse(doc.created_from_portal)

	def test_an_item_priced_only_in_another_unit_is_offered_in_that_unit(self):
		if not frappe.db.exists("UOM", "_Test Portal Kg"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "_Test Portal Kg"}).insert(ignore_permissions=True)
		self.item_code = self.make_item(uoms=[{"uom": "_Test Portal Kg", "conversion_factor": 1}])
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": self.item_code,
				"price_list": self.price_list,
				"price_list_rate": 3444,
				"uom": "_Test Portal Kg",
			}
		).insert(ignore_permissions=True)

		with self.set_user(self.user):
			listed = get_orderable_items(self.customer, self.company, search=self.item_code).data["rows"][0]

		self.assertEqual((listed["uom"], listed["rate"]), ("_Test Portal Kg", 3444))

	def test_pricing_a_basket_saves_nothing(self):
		before = frappe.db.count("Sales Order", {"customer": self.customer})

		with self.set_user(self.user):
			priced = price_order(
				customer=self.customer,
				company=self.company,
				items=[{"item_code": self.item_code, "qty": 4}],
			).data

		self.assertEqual(priced["grand_total"], 400)
		self.assertIsNone(priced["name"])
		self.assertEqual(frappe.db.count("Sales Order", {"customer": self.customer}), before)

	def make_item_group(self, published=True):
		name = "_Test Portal Order Group " + frappe.generate_hash(length=6)
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": name,
				"parent_item_group": "All Item Groups",
				"publish_on_portal": int(published),
			}
		).insert(ignore_permissions=True)
		return name

	def categories(self, **params):
		with self.set_user(self.user):
			return get_order_categories(self.customer, **params).data

	def test_categories_list_only_groups_with_priced_items(self):
		group = self.make_item_group()
		empty_group = self.make_item_group()
		for _index in range(2):
			self.add_price(self.make_item(item_group=group), 10)
		self.make_item(item_group=empty_group)

		categories = {row["name"]: row["count"] for row in self.categories(search=group)["rows"]}
		self.assertEqual(categories[group], 2)
		self.assertNotIn(empty_group, {row["name"] for row in self.categories(search=empty_group)["rows"]})

	def test_items_not_published_on_the_portal_cannot_be_browsed_or_ordered(self):
		"""An item without Sell on Sourcing Portal is hidden and rejected when ordered."""
		hidden = self.make_item(publish_on_portal=0)
		self.add_price(hidden, 50)

		with self.set_user(self.user):
			listed = get_orderable_items(self.customer, self.company, search=hidden).data["rows"]
		self.assertEqual(listed, [])
		with self.assertRaises(frappe.ValidationError):
			self.order(items=[{"item_code": hidden, "qty": 1, "uom": "Nos"}])

	def test_groups_not_shown_on_the_portal_hide_their_items(self):
		"""A published item in an unpublished item group stays off the portal."""
		group = self.make_item_group(published=False)
		item = self.make_item(item_group=group)
		self.add_price(item, 10)

		self.assertEqual(self.categories(search=group)["rows"], [])
		with self.set_user(self.user):
			self.assertEqual(
				get_orderable_items(self.customer, self.company, item_group=group).data["rows"], []
			)

	def test_categories_are_paged_and_searchable(self):
		"""Categories come back a page at a time, with a total for All on the first page."""
		prefix = "_Test Portal Paging " + frappe.generate_hash(length=4)
		for index in range(3):
			name = f"{prefix} {index}"
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": name,
					"parent_item_group": "All Item Groups",
					"publish_on_portal": 1,
				}
			).insert(ignore_permissions=True)
			self.add_price(self.make_item(item_group=name), 10)

		first = self.categories(search=prefix, limit=2)
		second = self.categories(search=prefix, start=2, limit=2)

		self.assertEqual([row["name"] for row in first["rows"]], [f"{prefix} 0", f"{prefix} 1"])
		self.assertTrue(first["has_more"])
		self.assertEqual([row["name"] for row in second["rows"]], [f"{prefix} 2"])
		self.assertFalse(second["has_more"])
		self.assertIsNone(first["all_items"])
		self.assertGreaterEqual(self.categories()["all_items"], 4)

	def test_items_can_be_browsed_by_category(self):
		group = self.make_item_group()
		in_group = self.make_item(item_group=group)
		self.add_price(in_group, 10)

		with self.set_user(self.user):
			listed = [
				row["item_code"]
				for row in get_orderable_items(self.customer, self.company, item_group=group).data["rows"]
			]

		self.assertEqual(listed, [in_group])

	def test_clearing_a_draft_removes_its_items_on_the_desk(self):
		draft = self.order(qty=3)

		with self.set_user(self.user):
			cleared = clear_order(self.customer, draft["name"]).data

		self.assertEqual(cleared["items"], [])
		self.assertEqual(cleared["grand_total"], 0)
		self.assertFalse(frappe.db.exists("Sales Order Item", {"parent": draft["name"]}))
		self.assertEqual(
			frappe.db.get_value("Sales Order", draft["name"], ["total_qty", "net_total", "grand_total"]),
			(0, 0, 0),
		)
		self.assertEqual(
			frappe.db.get_value("Sales Order", draft["name"], "portal_submission_status"), "Pending"
		)

	def test_a_sent_order_cannot_be_cleared(self):
		draft = self.order()
		with self.set_user(self.user):
			submit_order(
				customer=self.customer,
				company=self.company,
				name=draft["name"],
				items=[{"item_code": self.item_code, "qty": 1, "uom": "Nos"}],
				delivery_date=add_days(nowdate(), 7),
			)
			self.assertRaisesRegex(
				frappe.ValidationError, "can no longer be changed", clear_order, self.customer, draft["name"]
			)

		self.assertTrue(frappe.db.exists("Sales Order Item", {"parent": draft["name"]}))

	def test_another_customer_cannot_clear_the_draft(self):
		draft = self.order()
		other, other_user = self.make_ordering_customer()

		with self.set_user(other_user):
			self.assertRaises(frappe.PermissionError, clear_order, other, draft["name"])

		self.assertTrue(frappe.db.exists("Sales Order Item", {"parent": draft["name"]}))

	def test_a_cleared_draft_can_be_filled_and_sent_again(self):
		draft = self.order(qty=3)

		with self.set_user(self.user):
			clear_order(self.customer, draft["name"])
			sent = submit_order(
				customer=self.customer,
				company=self.company,
				name=draft["name"],
				items=[{"item_code": self.item_code, "qty": 2, "uom": "Nos"}],
				delivery_date=add_days(nowdate(), 7),
			).data

		self.assertEqual(sent["grand_total"], 200)
		self.assertEqual(sent["status"], "Submitted")

	def require_po_document(self, required=1):
		current = frappe.db.get_single_value("Sourcing Settings", "require_po_document")
		self.addCleanup(frappe.db.set_single_value, "Sourcing Settings", "require_po_document", current)
		frappe.db.set_single_value("Sourcing Settings", "require_po_document", required)

	def upload_lpo(self, customer=None, user=None, filename="lpo.pdf"):
		try:
			with self.set_user(user or self.user):
				frappe.local.uploaded_file = blank_pdf()
				frappe.local.uploaded_filename = filename
				frappe.form_dict.customer = customer or self.customer
				return attach_po_document().data
		finally:
			frappe.local.uploaded_file = None
			frappe.local.uploaded_filename = None
			frappe.form_dict.pop("customer", None)

	def send(self, name, **extra):
		with self.set_user(self.user):
			return submit_order(
				customer=self.customer,
				name=name,
				items=[{"item_code": self.item_code, "qty": 1}],
				**extra,
			)

	def test_an_order_can_be_sent_without_a_delivery_date(self):
		"""Leaving the date empty sends the order with the order date as its delivery date."""
		draft = self.order(delivery_date=None)

		self.send(draft["name"])

		self.assertEqual(str(frappe.db.get_value("Sales Order", draft["name"], "delivery_date")), nowdate())

	def test_a_chosen_delivery_date_is_kept(self):
		"""A date picked after starting without one is stored on the order."""
		draft = self.order(delivery_date=None)
		self.send(draft["name"], delivery_date=add_days(nowdate(), 5))

		self.assertEqual(
			str(frappe.db.get_value("Sales Order", draft["name"], "delivery_date")), add_days(nowdate(), 5)
		)

	def test_a_po_number_needs_its_lpo_document_before_sending_when_required(self):
		"""With the setting on, a PO number needs its LPO file before sending."""
		self.require_po_document()
		draft = self.order(po_no="LPO-NEEDS-DOC")

		self.assertRaisesRegex(
			frappe.ValidationError,
			"Attach your LPO document",
			self.send,
			draft["name"],
			po_no="LPO-NEEDS-DOC",
		)

		upload = self.upload_lpo()
		self.send(draft["name"], po_no="LPO-NEEDS-DOC", po_document=upload["file_url"])

		attached = self.attached_lpo(draft["name"])
		self.assertEqual(attached.file_name, "LPO-NEEDS-DOC-LPO.pdf")
		self.assertEqual(
			(attached.attached_to_doctype, attached.attached_to_name), ("Sales Order", draft["name"])
		)
		self.assertFalse(
			frappe.db.exists("File", {"file_url": upload["file_url"], "attached_to_doctype": "Customer"})
		)

	def test_the_lpo_document_is_optional_when_the_setting_is_off_or_there_is_no_po_number(self):
		"""No LPO file is needed with the setting off or without a PO number."""
		self.require_po_document(0)
		self.send(self.order(po_no="LPO-OPTIONAL")["name"], po_no="LPO-OPTIONAL")

		self.require_po_document()
		self.send(self.order()["name"])

	def test_another_users_upload_cannot_be_used_as_the_lpo(self):
		"""A file uploaded by another customer's user cannot be attached."""
		other, other_user = self.make_ordering_customer()
		theirs = self.upload_lpo(customer=other, user=other_user)

		self.assertRaisesRegex(
			frappe.ValidationError,
			"not uploaded by you",
			self.order,
			po_no="LPO-STOLEN",
			po_document=theirs["file_url"],
		)

	def test_an_lpo_upload_is_scoped_to_the_callers_customer_and_file_types(self):
		"""Uploads are refused for other customers and for disallowed file types."""
		other, _other_user = self.make_ordering_customer()

		self.assertRaises(frappe.PermissionError, self.upload_lpo, customer=other)
		self.assertRaisesRegex(frappe.ValidationError, "not accepted", self.upload_lpo, filename="lpo.exe")

	def test_an_lpo_upload_is_refused_when_ordering_is_off(self):
		"""Uploads are refused while portal ordering is turned off."""
		frappe.db.set_single_value("Sourcing Settings", "allow_customer_sales_orders", 0)
		self.assertRaises(frappe.PermissionError, self.upload_lpo)

	def attached_lpo(self, order):
		file_url = frappe.db.get_value("Sales Order", order, "portal_po_document")
		return frappe.get_doc(
			"File",
			{"file_url": file_url, "attached_to_doctype": "Sales Order", "attached_to_name": order},
		)

	def test_the_lpo_document_is_renamed_after_the_po_number_when_saved(self):
		"""The uploaded LPO is stored as the PO number followed by -LPO, keeping its file type."""
		upload = self.upload_lpo(filename="scan from phone.pdf")
		draft = self.order(po_no="PO/2026/77", po_document=upload["file_url"])

		attached = self.attached_lpo(draft["name"])
		self.assertEqual(attached.file_name, "PO-2026-77-LPO.pdf")
		self.assertIn("PO-2026-77-LPO", attached.file_url)
		self.assertEqual(draft["po_document"]["file_url"], attached.file_url)
		self.assertTrue(attached.exists_on_disk())

	def test_changing_the_po_number_renames_the_attached_lpo(self):
		"""Saving again under a new PO number renames the same document to match."""
		upload = self.upload_lpo()
		draft = self.order(po_no="PO-OLD-1", po_document=upload["file_url"])
		first = self.attached_lpo(draft["name"])

		with self.set_user(self.user):
			save_order(
				customer=self.customer,
				name=draft["name"],
				items=[{"item_code": self.item_code, "qty": 1}],
				po_no="PO-NEW-2",
				po_document=first.file_url,
			)

		second = self.attached_lpo(draft["name"])
		self.assertEqual(second.file_name, "PO-NEW-2-LPO.pdf")
		self.assertFalse(frappe.db.exists("File", first.name))
		self.assertEqual(
			frappe.db.count(
				"File", {"attached_to_doctype": "Sales Order", "attached_to_name": draft["name"]}
			),
			1,
		)


class TestPortalOrderFields(CustomerOrderFixtures, IntegrationTestCase):
	"""Custom Sales Order fields picked in Sourcing Settings and filled in by the customer on the portal."""

	cost_centre = "test_portal_cost_centre_code"
	channel = "test_portal_sales_channel"
	cost_centre_label = "_Test Cost Centre Code"
	channel_label = "_Test Sales Channel"
	desk_reference = "test_portal_desk_reference"
	desk_line_note = "test_portal_desk_line_note"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_custom_fields(
			{
				"Sales Order": [
					{
						"fieldname": cls.cost_centre,
						"label": cls.cost_centre_label,
						"fieldtype": "Data",
						"insert_after": "po_no",
					},
					{
						"fieldname": cls.channel,
						"label": cls.channel_label,
						"fieldtype": "Select",
						"options": "\nRetail\nWholesale",
						"description": "Where the goods will be sold.",
						"insert_after": cls.cost_centre,
					},
					{
						"fieldname": cls.desk_reference,
						"label": "_Test Desk Reference",
						"fieldtype": "Data",
						"insert_after": cls.channel,
					},
				],
				"Sales Order Item": [
					{
						"fieldname": cls.desk_line_note,
						"label": "_Test Desk Line Note",
						"fieldtype": "Data",
						"insert_after": "item_name",
					},
				],
			},
			update=True,
		)
		frappe.db.commit()  # nosemgrep

	def setUp(self):
		super().setUp()
		self.use_order_fields({"fieldname": self.cost_centre, "mandatory": 1}, {"fieldname": self.channel})

	def test_the_portal_uses_the_sales_order_fields_as_they_are(self):
		"""Label, type, choices and help text come from the Sales Order field itself."""
		settings = frappe.get_single("Sourcing Settings")
		with self.set_user(self.user):
			form = get_order_form(self.customer).data

		self.assertEqual(
			[(row.label, row.field_type) for row in settings.portal_order_fields],
			[(self.cost_centre_label, "Short Text"), (self.channel_label, "Multiple Choice")],
		)
		self.assertEqual(
			[(field["label"], field["field_type"], field["mandatory"]) for field in form["fields"]],
			[(self.cost_centre_label, "Short Text", True), (self.channel_label, "Multiple Choice", False)],
		)
		self.assertEqual(form["fields"][1]["choices"], ["Retail", "Wholesale"])
		self.assertEqual(form["fields"][1]["description"], "Where the goods will be sold.")

	def test_only_custom_fields_the_portal_can_fill_are_accepted(self):
		"""Standard fields and the portal's own fields cannot be picked."""
		for fieldname in ("po_no", "created_from_portal", "_test_missing_field"):
			with self.subTest(fieldname=fieldname):
				self.assertRaisesRegex(
					frappe.ValidationError,
					"not a custom Sales Order field",
					self.use_order_fields,
					{"fieldname": fieldname},
				)

	def test_a_field_cannot_be_picked_twice(self):
		"""The same Sales Order field cannot appear in two rows."""
		self.assertRaisesRegex(
			frappe.ValidationError,
			"already in the list",
			self.use_order_fields,
			{"fieldname": self.channel},
			{"fieldname": self.channel},
		)

	def test_a_mandatory_order_field_is_needed_to_send_but_not_to_save(self):
		"""A draft saves without the mandatory field; sending waits until it is filled in."""
		draft = self.order(details={self.channel: "Retail"})
		self.assertIsNone(draft["details"][self.cost_centre])
		self.assertEqual(draft["details"][self.channel], "Retail")

		with self.set_user(self.user):
			self.assertRaisesRegex(
				frappe.ValidationError,
				"before sending",
				submit_order,
				customer=self.customer,
				name=draft["name"],
				company=self.company,
				items=[{"item_code": self.item_code, "qty": 2, "uom": "Nos"}],
				details={self.channel: "Retail"},
			)
			submit_order(
				customer=self.customer,
				name=draft["name"],
				company=self.company,
				items=[{"item_code": self.item_code, "qty": 2, "uom": "Nos"}],
				details={self.cost_centre: " CC-104 ", self.channel: "Retail"},
			)
			shown = get_sales_order(draft["name"], self.customer)

		self.assertEqual(frappe.db.get_value("Sales Order", draft["name"], self.cost_centre), "CC-104")
		self.assertIn(
			{"label": self.cost_centre_label, "field_type": "Short Text", "value": "CC-104"}, shown["details"]
		)

	def make_mandatory(self, doctype, fieldname):
		name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname})
		frappe.db.set_value("Custom Field", name, "reqd", 1)
		frappe.clear_cache(doctype=doctype)
		self.addCleanup(frappe.clear_cache, doctype=doctype)
		self.addCleanup(frappe.db.set_value, "Custom Field", name, "reqd", 0)

	def test_a_mandatory_custom_field_left_out_of_the_order_fields_does_not_block_the_portal(self):
		"""Custom mandatory fields on Sales Order or its items that the portal does not ask for are left to the desk."""
		self.make_mandatory("Sales Order", self.desk_reference)
		self.make_mandatory("Sales Order Item", self.desk_line_note)
		self.assertTrue(frappe.get_meta("Sales Order").get_field(self.desk_reference).reqd)
		self.assertTrue(frappe.get_meta("Sales Order Item").get_field(self.desk_line_note).reqd)

		draft = self.order(details={self.cost_centre: "CC-104"})
		with self.set_user(self.user):
			submit_order(
				customer=self.customer,
				name=draft["name"],
				company=self.company,
				items=[{"item_code": self.item_code, "qty": 2, "uom": "Nos"}],
				details={self.cost_centre: "CC-104"},
			)

		doc = frappe.get_doc("Sales Order", draft["name"])
		self.assertEqual(doc.portal_submission_status, "Submitted")
		self.assertFalse(doc.get(self.desk_reference))
		self.assertFalse(doc.items[0].get(self.desk_line_note))

	def test_a_value_outside_the_choices_is_refused(self):
		"""A choice the Sales Order field does not offer cannot be saved on an order."""
		self.assertRaisesRegex(
			frappe.ValidationError, "Choose one of the options", self.order, details={self.channel: "Export"}
		)

	def test_only_system_managers_can_list_or_change_order_fields(self):
		"""Listing the Sales Order fields and editing the table both need the System Manager role."""
		meta = frappe.get_meta("Sourcing Settings")
		sales_manager = make_test_user(["Sales Master Manager"], first_name="Sales").name
		system_manager = make_test_user(["System Manager"], first_name="System").name

		self.assertEqual(meta.get_field("portal_order_fields").permlevel, 1)
		self.assertNotIn(1, meta.get_permlevel_access("write", user=sales_manager))
		self.assertIn(1, meta.get_permlevel_access("write", user=system_manager))

		with self.set_user(sales_manager):
			self.assertRaises(frappe.PermissionError, get_sales_order_fields)
		with self.set_user(system_manager):
			listed = [field["fieldname"] for field in get_sales_order_fields()]

		self.assertIn(self.cost_centre, listed)
		self.assertIn(self.channel, listed)
		self.assertNotIn("po_no", listed)
		self.assertNotIn("created_from_portal", listed)
