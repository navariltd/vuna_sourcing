# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from vuna_sourcing.api.rfq import get_rfq, send_quote
from vuna_sourcing.api.supplier_quotation import get_supplier_quotation, get_supplier_quotations
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures


class TestSupplierQuotations(SourcingFixtures, IntegrationTestCase):
	"""What the supplier sees of the quotations they have sent."""

	def send(self, rfq, user, rate=100, valid_days=30):
		with self.set_user(user):
			return send_quote(
				rfq.name,
				items=self.lines(get_rfq(rfq.name), rate=rate),
				valid_till=add_days(nowdate(), valid_days),
			)

	def test_a_supplier_sees_the_quotations_they_sent(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		sent = self.send(rfq, user)

		with self.set_user(user):
			page = get_supplier_quotations()

		self.assertEqual([row["name"] for row in page["rows"]], [sent["quote"]["name"]])
		row = page["rows"][0]
		self.assertEqual(row["status"], "Draft", "the buyer has not submitted it yet")
		self.assertEqual(row["rfq"], rfq.name, "each quotation names the request it answers")
		self.assertEqual(row["items"], 1)
		self.assertEqual(row["total"], 500)

	def test_a_supplier_never_sees_another_suppliers_quotation(self):
		mine, user = self.make_supplier()
		theirs, other_user = self.make_supplier()
		self.send(self.make_rfq([mine]), user)
		self.send(self.make_rfq([theirs]), other_user)

		with self.set_user(user):
			page = get_supplier_quotations()

		self.assertEqual(len(page["rows"]), 1)
		self.assertEqual(page["rows"][0]["supplier"], mine)

	def test_the_status_is_the_one_erpnext_keeps(self):
		"""Draft, Submitted, Expired and the rest are the doctype's own, not ours."""
		supplier, user = self.make_supplier()
		sent = self.send(self.make_rfq([supplier]), user)
		quote = frappe.get_doc("Supplier Quotation", sent["quote"]["name"])

		quote.flags.ignore_permissions = True
		quote.submit()

		with self.set_user(user):
			self.assertEqual(get_supplier_quotations()["rows"][0]["status"], "Submitted")

		from erpnext.buying.doctype.supplier_quotation.supplier_quotation import set_expired_status

		frappe.db.set_value("Supplier Quotation", quote.name, "valid_till", add_days(nowdate(), -1))
		set_expired_status()

		with self.set_user(user):
			self.assertEqual(get_supplier_quotations()["rows"][0]["status"], "Expired")

	def test_a_supplier_opens_the_quotation_they_sent(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		sent = self.send(rfq, user)

		with self.set_user(user):
			detail = get_supplier_quotation(sent["quote"]["name"])

		self.assertEqual(detail["supplier"], supplier)
		self.assertEqual(detail["status"], "Draft")
		self.assertEqual(detail["rfq"], rfq.name)
		self.assertEqual(detail["total"], 500)
		self.assertEqual(detail["items"][0]["rate"], 100)
		self.assertEqual(detail["items"][0]["qty"], 5)

	def test_a_supplier_cannot_open_another_suppliers_quotation(self):
		mine, user = self.make_supplier()
		theirs, other_user = self.make_supplier()
		self.send(self.make_rfq([mine]), user)
		sent = self.send(self.make_rfq([theirs]), other_user)

		with self.set_user(user):
			self.assertRaises(frappe.PermissionError, get_supplier_quotation, sent["quote"]["name"])

	def test_the_list_searches_and_pages(self):
		supplier, user = self.make_supplier()
		for _ in range(3):
			self.send(self.make_rfq([supplier]), user)

		with self.set_user(user):
			page = get_supplier_quotations(start=0, limit=2)
			self.assertEqual(len(page["rows"]), 2)
			self.assertEqual(page["total"], 3)

			one = page["rows"][0]["name"]
			found = get_supplier_quotations(search=one[-5:])

		self.assertEqual([row["name"] for row in found["rows"]], [one])
