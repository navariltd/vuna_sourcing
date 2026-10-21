# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from vuna_sourcing.api.transactions.supplier import (
	decline_quote,
	get_rfq,
	get_rfqs,
	get_supplier_quotations,
	save_quote,
	send_quote,
)
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures


class TestSupplierQuoteDrafts(SourcingFixtures, IntegrationTestCase):
	"""A supplier can keep a quote as a draft, and the buyer's side does not see it until it is sent."""

	def save_draft(self, rfq, user, **fields):
		with self.set_user(user):
			return save_quote(rfq.name, items=self.lines(get_rfq(rfq.name), rate=0), **fields).data

	def quote_name(self, detail) -> str:
		return detail["quote"]["name"]

	def test_a_draft_can_be_saved_half_finished(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		detail = self.save_draft(rfq, user)

		self.assertEqual(detail["status"], "Draft")
		self.assertTrue(detail["can_quote"], "a draft can still be edited and sent")
		quote = frappe.get_doc("Supplier Quotation", self.quote_name(detail))
		self.assertEqual(quote.supplier_submission_status, "Pending")
		self.assertEqual(quote.docstatus, 0)
		self.assertNotEqual(
			frappe.db.get_value("Request for Quotation Supplier", {"parent": rfq.name}, "quote_status"),
			"Received",
			"the request does not count a draft as a reply",
		)

		with self.set_user(user):
			self.assertEqual(get_rfqs()["counts"], {"Draft": 1})

	def test_saving_again_updates_the_same_draft(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		first = self.save_draft(rfq, user)

		with self.set_user(user):
			second = save_quote(
				rfq.name, items=self.lines(get_rfq(rfq.name), rate=80), quotation_number="Q-7"
			).data

		self.assertEqual(self.quote_name(first), self.quote_name(second))
		self.assertEqual(frappe.db.count("Supplier Quotation", {"supplier": supplier}), 1)
		self.assertEqual(second["items"][0]["rate"], 80)
		self.assertEqual(second["quote"]["quotation_number"], "Q-7")

	def test_sending_finalises_the_draft(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		draft = self.save_draft(rfq, user)

		with self.set_user(user):
			sent = send_quote(
				rfq.name, items=self.lines(get_rfq(rfq.name)), valid_till=add_days(nowdate(), 30)
			)

		self.assertEqual(self.quote_name(sent), self.quote_name(draft), "the draft is sent, not copied")
		self.assertEqual(sent["status"], "Submitted")
		self.assertFalse(sent["can_quote"])
		self.assertEqual(
			frappe.db.get_value("Supplier Quotation", self.quote_name(sent), "supplier_submission_status"),
			"Submitted",
		)

	def test_a_draft_still_needs_every_price_before_it_is_sent(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		draft = self.save_draft(rfq, user)

		with self.set_user(user):
			self.assertRaises(
				frappe.ValidationError,
				send_quote,
				rfq.name,
				items=self.lines(draft, rate=0),
				valid_till=add_days(nowdate(), 30),
			)

		self.assertEqual(
			frappe.db.get_value("Supplier Quotation", self.quote_name(draft), "supplier_submission_status"),
			"Pending",
		)

	def test_declining_throws_the_draft_away(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		draft = self.save_draft(rfq, user)

		with self.set_user(user):
			detail = decline_quote(rfq.name, reason="Out of stock")

		self.assertEqual(detail["status"], "Declined")
		self.assertFalse(frappe.db.exists("Supplier Quotation", self.quote_name(draft)))

	def test_no_draft_once_the_request_has_closed(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier], required_by=add_days(nowdate(), -1))

		with self.set_user(user):
			self.assertRaises(frappe.ValidationError, save_quote, rfq.name, items=[])

	def test_buyers_do_not_see_a_draft_until_it_is_sent(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		name = self.quote_name(self.save_draft(rfq, user))
		buyer = make_test_user(["Purchase User"], first_name="Buyer").name

		with self.set_user(buyer):
			self.assertNotIn(name, frappe.get_list("Supplier Quotation", pluck="name"))
			self.assertFalse(frappe.has_permission("Supplier Quotation", doc=name))

		with self.set_user(user):
			send_quote(rfq.name, items=self.lines(get_rfq(rfq.name)), valid_till=add_days(nowdate(), 30))
		self.open_bids(rfq)

		with self.set_user(buyer):
			self.assertIn(name, frappe.get_list("Supplier Quotation", pluck="name"))
			self.assertTrue(frappe.has_permission("Supplier Quotation", doc=name))

	def test_no_desk_user_sees_drafts_not_even_admins(self):
		supplier, user = self.make_supplier()
		name = self.quote_name(self.save_draft(self.make_rfq([supplier]), user))
		system_manager = make_test_user(["Purchase User", "System Manager"], first_name="Manager").name

		for viewer in (system_manager, "Administrator"):
			with self.set_user(viewer):
				self.assertNotIn(name, frappe.get_list("Supplier Quotation", pluck="name"))

		with self.set_user(system_manager):
			self.assertFalse(frappe.has_permission("Supplier Quotation", doc=name))

	def test_the_supplier_still_sees_their_own_draft(self):
		supplier, user = self.make_supplier()
		name = self.quote_name(self.save_draft(self.make_rfq([supplier]), user))

		with self.set_user(user):
			self.assertEqual([row["name"] for row in get_supplier_quotations()["rows"]], [name])

	def test_a_draft_cannot_be_submitted(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		name = self.quote_name(self.save_draft(rfq, user))
		self.open_bids(rfq)

		quote = frappe.get_doc("Supplier Quotation", name)
		for row in quote.items:
			row.rate = 100
		quote.valid_till = add_days(nowdate(), 30)
		quote.flags.ignore_permissions = True
		quote.save()

		with self.assertRaisesRegex(frappe.ValidationError, "not finalised"):
			quote.submit()

	def test_a_sent_quote_can_be_submitted(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		with self.set_user(user):
			sent = send_quote(
				rfq.name, items=self.lines(get_rfq(rfq.name)), valid_till=add_days(nowdate(), 30)
			)
		self.open_bids(rfq)

		quote = frappe.get_doc("Supplier Quotation", self.quote_name(sent))
		quote.flags.ignore_permissions = True
		quote.submit()
		self.assertEqual(quote.docstatus, 1)

	def add_buying_price(self, rate):
		price_list = frappe.db.get_single_value("Buying Settings", "buying_price_list") or "Standard Buying"
		if not frappe.db.exists("Price List", price_list):
			frappe.get_doc(
				{"doctype": "Price List", "price_list_name": price_list, "buying": 1, "enabled": 1}
			).insert(ignore_permissions=True)
		existing = frappe.db.get_value("Item Price", {"item_code": self.item, "price_list": price_list})
		if existing:
			frappe.db.set_value("Item Price", existing, "price_list_rate", rate)
			return
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": self.item,
				"price_list": price_list,
				"price_list_rate": rate,
			}
		).insert(ignore_permissions=True)

	def test_a_draft_without_prices_keeps_the_prices_empty(self):
		self.add_buying_price(777)
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		detail = self.save_draft(rfq, user)

		self.assertIsNone(detail["items"][0]["rate"], "the supplier never typed a price")
		quote = frappe.get_doc("Supplier Quotation", self.quote_name(detail))
		self.assertEqual(
			[(row.rate, row.price_list_rate) for row in quote.items],
			[(0, 0)],
			"the buyer's own price list never fills in the supplier's prices",
		)
