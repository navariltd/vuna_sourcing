# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_debit_note
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from vuna_sourcing.api.transactions.supplier import (
	get_purchase_invoice,
	get_purchase_invoices,
	get_purchase_order,
	get_purchase_orders,
)
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures


class TestSupplierTransactions(SourcingFixtures, IntegrationTestCase):
	"""The orders and invoices a supplier can see, run as the supplier."""

	def make_order(self, supplier, submit=True, qty=5, rate=100):
		order = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": supplier,
				"company": self.company,
				"transaction_date": nowdate(),
				"schedule_date": add_days(nowdate(), 7),
				"currency": frappe.get_cached_value("Company", self.company, "default_currency"),
				"conversion_rate": 1,
				"items": [
					{
						"item_code": self.item,
						"qty": qty,
						"rate": rate,
						"uom": "Nos",
						"conversion_factor": 1,
						"warehouse": self.warehouse,
						"schedule_date": add_days(nowdate(), 7),
					}
				],
			}
		)
		order.flags.ignore_permissions = True
		order.insert()
		if submit:
			order.submit()
		return order

	def make_invoice(self, supplier, submit=True, qty=5, rate=100):
		invoice = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"company": self.company,
				"posting_date": nowdate(),
				"due_date": add_days(nowdate(), 30),
				"bill_no": "INV-" + frappe.generate_hash(length=6),
				"currency": frappe.get_cached_value("Company", self.company, "default_currency"),
				"conversion_rate": 1,
				"items": [
					{
						"item_code": self.item,
						"qty": qty,
						"rate": rate,
						"uom": "Nos",
						"conversion_factor": 1,
					}
				],
			}
		)
		invoice.flags.ignore_permissions = True
		invoice.insert()
		if submit:
			invoice.submit()
		return invoice

	def test_a_supplier_sees_their_own_orders(self):
		supplier, user = self.make_supplier()
		order = self.make_order(supplier)

		with self.set_user(user):
			page = get_purchase_orders()

		self.assertEqual([row["name"] for row in page["rows"]], [order.name])
		row = page["rows"][0]
		self.assertEqual(row["grand_total"], 500)
		self.assertEqual(row["received"], 0, "nothing delivered yet")
		self.assertEqual(row["status"], order.status)

	def test_a_draft_order_reaches_the_supplier_so_they_can_confirm_it(self):
		"""Staff submit on the desk once the supplier says the draft is right."""
		supplier, user = self.make_supplier()
		order = self.make_order(supplier, submit=False)

		with self.set_user(user):
			page = get_purchase_orders()
			detail = get_purchase_order(order.name)

		self.assertEqual([row["name"] for row in page["rows"]], [order.name])
		self.assertEqual(page["rows"][0]["status"], "Draft")
		self.assertEqual(detail["name"], order.name, "and it opens, rather than refusing")

	def test_a_supplier_never_sees_another_suppliers_order(self):
		mine, user = self.make_supplier()
		theirs, _other = self.make_supplier()
		self.make_order(mine)
		self.make_order(theirs)

		with self.set_user(user):
			page = get_purchase_orders()

		self.assertEqual(len(page["rows"]), 1)
		self.assertEqual(page["rows"][0]["supplier"], mine)

	def test_a_supplier_sees_their_own_invoices_with_what_is_outstanding(self):
		supplier, user = self.make_supplier()
		invoice = self.make_invoice(supplier)

		with self.set_user(user):
			page = get_purchase_invoices()

		row = page["rows"][0]
		self.assertEqual(row["name"], invoice.name)
		self.assertEqual(row["bill_no"], invoice.bill_no, "their own invoice number")
		self.assertEqual(row["grand_total"], 500)
		self.assertEqual(row["outstanding_amount"], 500)
		self.assertEqual(row["status"], invoice.status)

	def test_a_draft_invoice_reaches_the_supplier_and_opens(self):
		supplier, user = self.make_supplier()
		invoice = self.make_invoice(supplier, submit=False)

		with self.set_user(user):
			page = get_purchase_invoices()
			detail = get_purchase_invoice(invoice.name)

		self.assertEqual([row["name"] for row in page["rows"]], [invoice.name])
		self.assertEqual(detail["name"], invoice.name)

	def test_a_cancelled_order_is_gone_from_the_portal(self):
		supplier, user = self.make_supplier()
		order = self.make_order(supplier)
		order.flags.ignore_permissions = True
		order.cancel()

		with self.set_user(user):
			self.assertEqual(get_purchase_orders()["rows"], [])
			self.assertRaises(frappe.PermissionError, get_purchase_order, order.name)

	def test_a_supplier_never_sees_another_suppliers_invoice(self):
		mine, user = self.make_supplier()
		theirs, _other = self.make_supplier()
		self.make_invoice(mine)
		self.make_invoice(theirs)

		with self.set_user(user):
			page = get_purchase_invoices()

		self.assertEqual(len(page["rows"]), 1)
		self.assertEqual(page["rows"][0]["supplier"], mine)

	def test_both_lists_search_and_page(self):
		supplier, user = self.make_supplier()
		orders = [self.make_order(supplier) for _ in range(3)]

		with self.set_user(user):
			first = get_purchase_orders(start=0, limit=2)
			found = get_purchase_orders(search=orders[0].name[-5:])

		self.assertEqual(len(first["rows"]), 2)
		self.assertEqual(first["total"], 3)
		self.assertEqual([row["name"] for row in found["rows"]], [orders[0].name])

	def test_a_supplier_opens_an_order_and_sees_what_is_still_outstanding(self):
		supplier, user = self.make_supplier()
		order = self.make_order(supplier, qty=5, rate=100)

		with self.set_user(user):
			detail = get_purchase_order(order.name)

		self.assertEqual(detail["name"], order.name)
		self.assertEqual(detail["grand_total"], 500)
		self.assertEqual(detail["status"], order.status)
		self.assertEqual(detail["receipts"], [], "nothing received yet")

		line = detail["items"][0]
		self.assertEqual(line["qty"], 5)
		self.assertEqual(line["received_qty"], 0)
		self.assertEqual(line["outstanding_qty"], 5, "the whole order is still to come")

	def test_a_supplier_opens_an_invoice_and_sees_what_settled_it(self):
		supplier, user = self.make_supplier()
		invoice = self.make_invoice(supplier)

		with self.set_user(user):
			detail = get_purchase_invoice(invoice.name)

		self.assertEqual(detail["bill_no"], invoice.bill_no)
		self.assertEqual(detail["outstanding_amount"], 500)
		self.assertEqual(detail["payments"], [], "nothing paid yet")
		self.assertIsNone(detail["hold_reason"])
		self.assertEqual(detail["items"][0]["amount"], 500)

	def test_an_invoice_on_hold_carries_the_reason_the_buyer_typed(self):
		supplier, user = self.make_supplier()
		invoice = self.make_invoice(supplier)
		frappe.db.set_value(
			"Purchase Invoice",
			invoice.name,
			{
				"on_hold": 1,
				"hold_comment": "Waiting on the delivery note for the second batch.",
				"release_date": add_days(nowdate(), 14),
			},
		)

		with self.set_user(user):
			detail = get_purchase_invoice(invoice.name)

		self.assertTrue(detail["on_hold"])
		self.assertEqual(detail["hold_reason"], "Waiting on the delivery note for the second batch.")
		self.assertEqual(getdate(detail["release_date"]), getdate(add_days(nowdate(), 14)))

	def test_an_invoice_that_is_not_held_carries_no_hold_details(self):
		supplier, user = self.make_supplier()
		invoice = self.make_invoice(supplier)

		with self.set_user(user):
			detail = get_purchase_invoice(invoice.name)

		self.assertFalse(detail["on_hold"])
		self.assertIsNone(detail["hold_reason"])
		self.assertIsNone(detail["release_date"])

	def test_a_supplier_cannot_open_another_suppliers_order_or_invoice(self):
		_mine, user = self.make_supplier()
		theirs, _other = self.make_supplier()
		order = self.make_order(theirs)
		invoice = self.make_invoice(theirs)

		with self.set_user(user):
			self.assertRaises(frappe.PermissionError, get_purchase_order, order.name)
			self.assertRaises(frappe.PermissionError, get_purchase_invoice, invoice.name)

	def test_a_debit_note_is_listed_apart_from_invoices_and_linked_from_the_invoice(self):
		supplier, user = self.make_supplier()
		invoice = self.make_invoice(supplier)
		debit_note = make_debit_note(invoice.name)
		debit_note.flags.ignore_permissions = True
		debit_note.insert()
		debit_note.submit()

		with self.set_user(user):
			invoices = get_purchase_invoices()
			debit_notes = get_purchase_invoices(debit_notes=1)
			original = get_purchase_invoice(invoice.name)
			note = get_purchase_invoice(debit_note.name)

		self.assertEqual([row["name"] for row in invoices["rows"]], [invoice.name])
		self.assertEqual([row["name"] for row in debit_notes["rows"]], [debit_note.name])
		self.assertTrue(debit_notes["rows"][0]["is_return"])
		self.assertEqual([row.name for row in original["debit_notes"]], [debit_note.name])
		self.assertEqual(note["return_against"], invoice.name)
