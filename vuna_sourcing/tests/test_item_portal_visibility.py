# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from vuna_sourcing.api.transactions.customer_orders import get_orderable_items
from vuna_sourcing.overrides.server.item import FAILED, PASSED, SKIPPED, get_portal_visibility
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.test_customer_orders import CustomerOrderFixtures, restrict_to

ITEM = "Item"


class TestItemPortalVisibility(CustomerOrderFixtures, IntegrationTestCase):
	"""The Sourcing button on Item explains why an item is or is not offered on the portal."""

	def setUp(self):
		super().setUp()
		self.staff = make_test_user(["Item Manager", "Sales User"], first_name="Items").name

	def make_item_group(self, published=True, name=None):
		name = name or "_Test Portal Visibility Group " + frappe.generate_hash(length=6)
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": name,
				"parent_item_group": "All Item Groups",
				"publish_on_portal": int(published),
			}
		).insert(ignore_permissions=True)
		return name

	def visibility(self, item=None, company=None, customer=None):
		with self.set_user(self.staff):
			return get_portal_visibility(item or self.item_code, company=company, customer=customer).data

	def failing(self, result) -> list[str]:
		return [
			check["label"]
			for section in result["sections"]
			for check in section["checks"]
			if check["status"] == FAILED
		]

	def status_of(self, result, section_label: str) -> str:
		section = next(section for section in result["sections"] if section["label"] == section_label)
		return section["checks"][0]["status"]

	def offered(self, item_code: str) -> bool:
		with self.set_user(self.user):
			rows = get_orderable_items(self.customer, self.company, search=item_code).data["rows"]
		return any(row["item_code"] == item_code for row in rows)

	def test_a_ready_item_is_reported_as_shown(self):
		"""A published, priced item in a published group passes every check."""
		result = self.visibility(company=self.company)

		self.assertTrue(result["shown"])
		self.assertEqual(result["blocking"], 0)
		self.assertEqual(self.failing(result), [])

	def test_the_report_agrees_with_the_portal_catalogue(self):
		"""What the dialog reports matches what the customer is actually offered."""
		hidden = self.make_item(publish_on_portal=0)
		self.add_price(hidden, 50)

		self.assertTrue(self.visibility(company=self.company)["shown"])
		self.assertTrue(self.offered(self.item_code))
		self.assertFalse(self.visibility(hidden, company=self.company)["shown"])
		self.assertFalse(self.offered(hidden))

	def test_the_default_ordering_company_is_used_when_none_is_picked(self):
		"""Without a company picked, the check uses the Default Ordering Company."""
		self.use_default_company(self.company)

		result = self.visibility()

		self.assertEqual(result["company"], self.company)
		self.assertTrue(result["shown"])

	def test_without_any_company_the_missing_company_is_reported(self):
		"""With no company picked and no default, the dialog says a company is missing."""
		result = self.visibility()

		self.assertFalse(result["shown"])
		self.assertIn("No company to order from", self.failing(result))

	def test_an_unpublished_item_says_which_box_to_tick(self):
		"""An item without Sell on Sourcing Portal is reported with a fix that ticks it."""
		frappe.db.set_value(ITEM, self.item_code, "publish_on_portal", 0)

		result = self.visibility(company=self.company)
		check = next(
			check
			for section in result["sections"]
			for check in section["checks"]
			if check["status"] == FAILED
		)

		self.assertFalse(result["shown"])
		self.assertEqual(check["action"]["field"], "publish_on_portal")
		self.assertEqual(check["action"]["value"], 1)

	def test_an_unpublished_item_group_is_reported(self):
		"""An item whose group is not shown on the portal is reported with a fix for the group."""
		group = self.make_item_group(published=False)
		item = self.make_item(item_group=group)
		self.add_price(item, 10)

		result = self.visibility(item, company=self.company)

		self.assertFalse(result["shown"])
		self.assertEqual(self.status_of(result, "Category"), FAILED)
		self.assertFalse(self.offered(item))

	def test_a_template_and_a_disabled_item_are_reported(self):
		"""Templates and disabled items are reported as never offered."""
		frappe.db.set_value(ITEM, self.item_code, {"disabled": 1, "has_variants": 1})

		failing = self.failing(self.visibility(company=self.company))

		self.assertIn("The item is disabled", failing)
		self.assertIn("This is a template item", failing)

	def test_a_past_end_of_life_is_reported(self):
		"""An item past its end of life is reported with the date."""
		frappe.db.set_value(ITEM, self.item_code, "end_of_life", add_days(nowdate(), -1))

		self.assertIn("End of life has passed", self.failing(self.visibility(company=self.company)))

	def test_an_item_without_a_portal_price_is_reported(self):
		"""An item with no price on the portal price list is reported with a fix that adds one."""
		item = self.make_item()

		result = self.visibility(item, company=self.company)
		price = next(section for section in result["sections"] if section["label"] == "Price")["checks"][0]

		self.assertEqual(price["status"], FAILED)
		self.assertEqual(price["action"]["doctype"], "Item Price")
		self.assertEqual(price["action"]["values"]["price_list"], self.price_list)

	def test_an_expired_price_is_explained(self):
		"""A price that ended is reported as unusable with the date it ended."""
		item = self.make_item()
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": item,
				"price_list": self.price_list,
				"price_list_rate": 10,
				"valid_from": add_days(nowdate(), -30),
				"valid_upto": add_days(nowdate(), -2),
			}
		).insert(ignore_permissions=True)

		result = self.visibility(item, company=self.company)
		price = next(section for section in result["sections"] if section["label"] == "Price")["checks"][0]

		self.assertEqual(price["status"], FAILED)
		self.assertIn("ended on", price["detail"])

	def test_a_price_for_one_customer_counts_only_for_that_customer(self):
		"""A customer's own price makes the item visible to them and to no one else."""
		item = self.make_item()
		self.add_price(item, 20, customer=self.customer)
		other, _user = self.make_ordering_customer()

		self.assertTrue(self.visibility(item, company=self.company, customer=self.customer)["shown"])
		self.assertFalse(self.visibility(item, company=self.company, customer=other)["shown"])
		self.assertFalse(self.visibility(item, company=self.company)["shown"])

	def test_a_company_restriction_is_reported(self):
		"""An item restricted to another company is reported as hidden for the picked company."""
		item = self.make_item(company=self.other_company)
		self.add_price(item, 10)

		result = self.visibility(item, company=self.company)

		self.assertFalse(result["shown"])
		self.assertEqual(self.status_of(result, "Company"), FAILED)
		self.assertTrue(self.visibility(item, company=self.other_company)["shown"])

	def test_a_customer_who_cannot_order_from_the_company_is_reported(self):
		"""A customer whose allowed companies leave out the picked company is reported."""
		restrict_to(frappe.get_doc("Customer", self.customer), [self.other_company])

		result = self.visibility(company=self.company, customer=self.customer)

		self.assertFalse(result["shown"])
		self.assertEqual(self.status_of(result, "Customer"), FAILED)

	def test_customer_checks_are_skipped_until_a_customer_is_picked(self):
		"""Without a customer the customer check is skipped rather than failed."""
		self.assertEqual(self.status_of(self.visibility(company=self.company), "Customer"), SKIPPED)

	def test_turning_ordering_off_is_reported(self):
		"""With customer ordering off in Sourcing Settings the item is reported hidden."""
		frappe.db.set_single_value("Sourcing Settings", "allow_customer_sales_orders", 0)

		result = self.visibility(company=self.company)

		self.assertFalse(result["shown"])
		self.assertIn("Customer ordering is off", self.failing(result))

	def test_names_are_escaped_in_the_report(self):
		"""Names shown in the dialog are escaped so they cannot inject markup."""
		group = self.make_item_group(
			published=False, name="_Test Tools & Parts " + frappe.generate_hash(length=4)
		)
		item = self.make_item(item_group=group)

		result = self.visibility(item, company=self.company)
		labels = " ".join(check["label"] for section in result["sections"] for check in section["checks"])

		self.assertNotIn("Tools & Parts", labels)
		self.assertIn("Tools &amp; Parts", labels)

	def test_a_portal_customer_cannot_run_the_check(self):
		"""Portal users have no Read on Item, so the check is refused."""
		with self.set_user(self.user):
			self.assertRaises(frappe.PermissionError, get_portal_visibility, self.item_code)

	def test_every_check_has_a_known_status(self):
		"""Each check reports passed, failed or skipped."""
		result = self.visibility(company=self.company, customer=self.customer)

		for section in result["sections"]:
			for check in section["checks"]:
				self.assertIn(check["status"], (PASSED, FAILED, SKIPPED))
