# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate
from frappe.www.printview import validate_print_permission

from vuna_sourcing.api.transactions.customer import (
	get_account_statement,
	get_dashboard,
	get_delivery_note,
	get_delivery_notes,
	get_quotation,
	get_quotations,
	get_sales_invoice,
	get_sales_invoices,
	get_sales_order,
	get_sales_orders,
)
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures


class TestCustomerTransactions(SourcingFixtures, IntegrationTestCase):
	"""The quotations, orders, deliveries and invoices a customer can see, run as the customer."""

	def line(self, qty, rate, **extra):
		return {
			"item_code": self.item,
			"qty": qty,
			"rate": rate,
			"uom": "Nos",
			"conversion_factor": 1,
			**extra,
		}

	def currency(self):
		return frappe.get_cached_value("Company", self.company, "default_currency")

	def save(self, doc, submit):
		doc.flags.ignore_permissions = True
		doc.insert()
		if submit:
			doc.submit()
		return doc

	def make_quotation(self, customer, submit=True, qty=5, rate=100):
		return self.save(
			frappe.get_doc(
				{
					"doctype": "Quotation",
					"quotation_to": "Customer",
					"party_name": customer,
					"company": self.company,
					"transaction_date": nowdate(),
					"valid_till": add_days(nowdate(), 30),
					"currency": self.currency(),
					"conversion_rate": 1,
					"items": [self.line(qty, rate)],
				}
			),
			submit,
		)

	def make_order(self, customer, submit=True, qty=5, rate=100, po_no=None):
		return self.save(
			frappe.get_doc(
				{
					"doctype": "Sales Order",
					"customer": customer,
					"company": self.company,
					"po_no": po_no,
					"transaction_date": nowdate(),
					"delivery_date": add_days(nowdate(), 7),
					"currency": self.currency(),
					"conversion_rate": 1,
					"items": [
						self.line(qty, rate, warehouse=self.warehouse, delivery_date=add_days(nowdate(), 7))
					],
				}
			),
			submit,
		)

	def deliver(self, order, submit=True):
		return self.save(make_delivery_note(order.name), submit)

	def invoice(self, order, submit=True):
		invoice = make_sales_invoice(order.name)
		invoice.due_date = add_days(nowdate(), 30)
		return self.save(invoice, submit)

	def test_a_customer_sees_their_submitted_quotation(self):
		customer, user = self.make_customer()
		quotation = self.make_quotation(customer)

		with self.set_user(user):
			page = get_quotations()
			detail = get_quotation(quotation.name)

		self.assertEqual([row["name"] for row in page["rows"]], [quotation.name])
		self.assertEqual(page["rows"][0]["grand_total"], 500)
		self.assertEqual(detail["items"][0]["amount"], 500)
		self.assertEqual(detail["sales_orders"], [], "nothing ordered from it yet")

	def test_a_draft_quotation_stays_on_the_desk(self):
		customer, user = self.make_customer()
		draft = self.make_quotation(customer, submit=False)

		with self.set_user(user):
			self.assertEqual(get_quotations()["rows"], [])
			self.assertRaises(frappe.PermissionError, get_quotation, draft.name)

	def test_a_draft_order_stays_on_the_desk(self):
		customer, user = self.make_customer()
		draft = self.make_order(customer, submit=False)

		with self.set_user(user):
			self.assertEqual(get_sales_orders()["rows"], [])
			self.assertRaises(frappe.PermissionError, get_sales_order, draft.name)

	def test_a_draft_delivery_or_invoice_stays_on_the_desk(self):
		customer, user = self.make_customer()
		order = self.make_order(customer)
		delivery = self.deliver(order, submit=False)
		invoice = self.invoice(order, submit=False)

		with self.set_user(user):
			self.assertEqual(get_delivery_notes()["rows"], [])
			self.assertEqual(get_sales_invoices()["rows"], [])
			self.assertRaises(frappe.PermissionError, get_delivery_note, delivery.name)
			self.assertRaises(frappe.PermissionError, get_sales_invoice, invoice.name)

	def test_a_cancelled_order_is_gone_from_the_portal(self):
		customer, user = self.make_customer()
		order = self.make_order(customer)
		order.flags.ignore_permissions = True
		order.cancel()

		with self.set_user(user):
			self.assertEqual(get_sales_orders()["rows"], [])
			self.assertRaises(frappe.PermissionError, get_sales_order, order.name)

	def test_a_customer_follows_an_order_through_delivery_and_invoice(self):
		customer, user = self.make_customer()
		order = self.make_order(customer, qty=5, rate=100)
		delivery = self.deliver(order)
		invoice = self.invoice(order)

		with self.set_user(user):
			orders = get_sales_orders()
			detail = get_sales_order(order.name)
			shipped = get_delivery_note(delivery.name)
			billed = get_sales_invoice(invoice.name)

		self.assertEqual(orders["rows"][0]["delivered"], 100)
		self.assertEqual(detail["items"][0]["outstanding_qty"], 0, "everything has shipped")
		self.assertEqual([row.name for row in detail["deliveries"]], [delivery.name])
		self.assertEqual(detail["invoices"], [invoice.name])
		self.assertEqual(shipped["sales_orders"], [order.name])
		self.assertEqual(billed["sales_orders"], [order.name])
		self.assertEqual(billed["outstanding_amount"], 500)
		self.assertEqual(billed["payments"], [], "nothing paid yet")

	def test_a_customer_finds_an_order_by_their_own_po_number(self):
		customer, user = self.make_customer()
		order = self.make_order(customer, po_no="PO-" + frappe.generate_hash(length=6))
		self.make_order(customer)

		with self.set_user(user):
			found = get_sales_orders(search=order.po_no)

		self.assertEqual([row["name"] for row in found["rows"]], [order.name])

	def test_a_customer_never_sees_another_customers_documents(self):
		mine, user = self.make_customer()
		theirs, _other = self.make_customer()
		quotation = self.make_quotation(theirs)
		order = self.make_order(theirs)
		delivery = self.deliver(order)
		invoice = self.invoice(order)
		self.make_order(mine)

		with self.set_user(user):
			self.assertEqual(get_quotations()["rows"], [])
			self.assertEqual([row["customer"] for row in get_sales_orders()["rows"]], [mine])
			self.assertEqual(get_delivery_notes()["rows"], [])
			self.assertEqual(get_sales_invoices()["rows"], [])
			self.assertRaises(frappe.PermissionError, get_quotation, quotation.name)
			self.assertRaises(frappe.PermissionError, get_sales_order, order.name)
			self.assertRaises(frappe.PermissionError, get_delivery_note, delivery.name)
			self.assertRaises(frappe.PermissionError, get_sales_invoice, invoice.name)
			self.assertRaises(frappe.PermissionError, get_sales_orders, theirs)

	def test_a_supplier_is_not_a_customer(self):
		customer, _user = self.make_customer()
		self.make_order(customer)
		_supplier, supplier_user = self.make_supplier()

		with self.set_user(supplier_user):
			self.assertEqual(get_sales_orders()["rows"], [])
			self.assertRaises(frappe.PermissionError, get_sales_orders, customer)

	def test_a_credit_note_is_listed_apart_from_invoices_and_linked_from_the_invoice(self):
		customer, user = self.make_customer()
		invoice = self.invoice(self.make_order(customer))
		credit_note = self.save(make_sales_return(invoice.name), submit=True)

		with self.set_user(user):
			invoices = get_sales_invoices()
			credit_notes = get_sales_invoices(credit_notes=1)
			original = get_sales_invoice(invoice.name)
			note = get_sales_invoice(credit_note.name)

		self.assertEqual([row["name"] for row in invoices["rows"]], [invoice.name])
		self.assertEqual([row["name"] for row in credit_notes["rows"]], [credit_note.name])
		self.assertTrue(credit_notes["rows"][0]["is_return"])
		self.assertEqual([row.name for row in original["credit_notes"]], [credit_note.name])
		self.assertEqual(note["return_against"], invoice.name)

	def test_a_customer_prints_their_submitted_order_but_not_a_draft_or_another_customers(self):
		mine, user = self.make_customer()
		theirs, _other = self.make_customer()
		submitted = self.make_order(mine)
		draft = self.make_order(mine, submit=False)
		other = self.make_order(theirs)

		with self.set_user(user):
			validate_print_permission(frappe.get_doc("Sales Order", submitted.name))
			for name in (draft.name, other.name):
				self.assertRaises(
					frappe.PermissionError,
					validate_print_permission,
					frappe.get_doc("Sales Order", name),
				)

	def test_a_customer_sees_what_they_owe_from_the_erpnext_receivable_report(self):
		mine, user = self.make_customer()
		theirs, _other = self.make_customer()
		invoice = self.invoice(self.make_order(mine, qty=5, rate=100))
		self.invoice(self.make_order(theirs))

		with self.set_user(user):
			frappe.local.session.sid = "a-browser-session"
			frappe.local.session.data = frappe._dict(kept=True)
			statement = get_account_statement()
			self.assertEqual(frappe.session.user, user, "the report runs elevated, then hands back")
			self.assertEqual(frappe.local.session.sid, "a-browser-session", "the login survives")
			self.assertTrue(frappe.local.session.data.kept)

		[section] = statement["companies"]
		self.assertEqual([row["voucher_no"] for row in section["rows"]], [invoice.name])
		self.assertEqual(section["totals"]["outstanding"], 500)

	def test_a_customer_cannot_ask_for_another_customers_statement(self):
		_mine, user = self.make_customer()
		theirs, _other = self.make_customer()

		with self.set_user(user):
			self.assertRaises(frappe.PermissionError, get_account_statement, theirs)

	def test_a_customers_dashboard_counts_what_needs_their_attention(self):
		mine, user = self.make_customer()
		theirs, _other = self.make_customer()
		quotation = self.make_quotation(mine)
		self.make_order(mine)
		invoice = self.invoice(self.make_order(mine, qty=5, rate=100))
		self.make_order(theirs)

		with self.set_user(user):
			dashboard = get_dashboard()

		self.assertEqual(dashboard["quotes_to_review"], 1)
		self.assertEqual([row.name for row in dashboard["quotes"]], [quotation.name])
		self.assertEqual(dashboard["open_orders"], 2, "only their own orders")
		self.assertEqual(dashboard["balance"]["outstanding"], invoice.outstanding_amount)
		self.assertEqual(dashboard["invoiced_by_month"][-1]["value"], invoice.base_grand_total)
		self.assertEqual(len(dashboard["invoiced_by_month"]), 12)

	def test_a_customer_cannot_open_another_customers_dashboard(self):
		_mine, user = self.make_customer()
		theirs, _other = self.make_customer()

		with self.set_user(user):
			self.assertRaises(frappe.PermissionError, get_dashboard, theirs)
