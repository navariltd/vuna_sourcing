# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from vuna_sourcing.api.transactions.customer import get_sales_order, get_sales_orders
from vuna_sourcing.api.transactions.customer_orders import (
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


class TestCustomerOrders(SourcingFixtures, IntegrationTestCase):
	"""Customers placing Sales Orders from the portal, run as the customer."""

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

	def setUp(self):
		current = frappe.db.get_single_value("Sourcing Settings", "allow_customer_sales_orders")
		self.addCleanup(
			frappe.db.set_single_value, "Sourcing Settings", "allow_customer_sales_orders", current
		)
		frappe.db.set_single_value("Sourcing Settings", "allow_customer_sales_orders", 1)
		selling_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
		self.addCleanup(frappe.db.set_single_value, "Selling Settings", "selling_price_list", selling_list)
		frappe.db.set_single_value("Selling Settings", "selling_price_list", self.price_list)

		self.customer, self.user = self.make_ordering_customer()
		self.item_code = self.make_item()
		self.add_price(self.item_code, 100)

	def make_ordering_customer(self):
		customer, user = self.make_customer()
		doc = frappe.get_doc("Customer", customer)
		doc.append("accounts", {"company": self.company})
		doc.save(ignore_permissions=True)
		return customer, user

	def make_item(self, company=None, **fields):
		return (
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "_Test Portal Order Item " + frappe.generate_hash(length=6),
					"item_group": self.item_group,
					"publish_on_portal": 1,
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"item_defaults": [
						{
							"company": company or self.company,
							"default_warehouse": frappe.get_all(
								"Warehouse",
								filters={"is_group": 0, "company": company or self.company},
								limit=1,
								pluck="name",
							)[0],
						}
					],
					**fields,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

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

	def add_address(self, customer, title):
		return (
			frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": title,
					"address_type": "Shipping",
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

	def test_a_customer_orders_only_from_companies_on_their_accounts(self):
		other_company = self.other_company

		self.assertRaises(frappe.ValidationError, self.order, company=other_company)

		customer, user = self.make_customer()
		with self.set_user(user):
			self.assertFalse(get_order_form(customer).ok)
			self.assertFalse(get_sales_orders(customer=customer)["can_order"])

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
		doc = frappe.get_doc(
			{
				"doctype": "Sales Order",
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
