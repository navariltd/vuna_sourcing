# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from vuna_sourcing.api.transactions.credit_requests import (
	get_credit_form,
	get_credit_request,
	get_credit_requests,
	get_creditable_invoices,
	resubmit_credit_request,
	submit_credit_request,
	withdraw_credit_request,
)
from vuna_sourcing.api.transactions.customer import get_sales_invoice
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures
from vuna_sourcing.vuna_sourcing.doctype.credit_note_request.credit_note_request import (
	DOCTYPE,
	make_credit_note,
)

SETTINGS = "Sourcing Settings"


class TestCreditNoteRequests(SourcingFixtures, IntegrationTestCase):
	"""Customers asking for a credit note against an invoice, and Accounts approving it on the desk."""

	second_item = "_Test Credit Request Item B"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		if not frappe.db.exists("Item", cls.second_item):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": cls.second_item,
					"item_name": cls.second_item,
					"item_group": frappe.get_all(
						"Item Group", filters={"is_group": 0}, limit=1, pluck="name"
					)[0],
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)
		cls.approver = make_test_user(["Accounts Manager", "Accounts User"], first_name="Approver").name

	def setUp(self):
		for field, value in (
			("allow_customer_credit_requests", 1),
			("notify_customer_of_credit_decisions", 0),
		):
			current = frappe.db.get_single_value(SETTINGS, field)
			self.addCleanup(frappe.db.set_single_value, SETTINGS, field, current)
			frappe.db.set_single_value(SETTINGS, field, value)

		self.customer, self.user = self.make_customer()

	def make_invoice(self, customer=None, lines=((5, 100), (3, 40))):
		items = [self.item, self.second_item]
		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer or self.customer,
				"company": self.company,
				"posting_date": nowdate(),
				"due_date": add_days(nowdate(), 30),
				"currency": frappe.get_cached_value("Company", self.company, "default_currency"),
				"conversion_rate": 1,
				"items": [
					{"item_code": items[idx], "qty": qty, "rate": rate, "uom": "Nos", "conversion_factor": 1}
					for idx, (qty, rate) in enumerate(lines)
				],
			}
		)
		invoice.flags.ignore_permissions = True
		invoice.insert()
		invoice.submit()
		return invoice

	def credit_directly(self, invoice, qty_by_row):
		credit_note = make_sales_return(invoice.name)
		credit_note.items = [row for row in credit_note.items if row.sales_invoice_item in qty_by_row]
		for row in credit_note.items:
			row.qty = -qty_by_row[row.sales_invoice_item]
		credit_note.flags.ignore_permissions = True
		credit_note.insert()
		credit_note.submit()
		return credit_note

	def ask(self, invoice, qty_by_row, reason="Damaged Goods", description=None):
		with self.set_user(self.user):
			return submit_credit_request(
				customer=self.customer,
				sales_invoice=invoice.name,
				items=[{"sales_invoice_item": row, "qty": qty} for row, qty in qty_by_row.items()],
				reason=reason,
				description=description,
			).data

	def review(self, name, method, **args):
		with self.set_user(self.approver):
			request = frappe.get_doc(DOCTYPE, name)
			getattr(request, method)(**args)
		return frappe.get_doc(DOCTYPE, name)

	def issue(self, name):
		with self.set_user(self.approver):
			credit_note = make_credit_note(name)
			credit_note.insert()
			credit_note.submit()
		return credit_note

	def test_a_customer_asks_to_credit_part_of_an_invoice(self):
		"""The request keeps only the lines asked for, priced at the invoice rate, and waits for review."""
		invoice = self.make_invoice()
		first, second = (row.name for row in invoice.items)

		request = self.ask(invoice, {first: 2, second: 0})

		self.assertEqual(request["status"], "Pending Review")
		self.assertEqual([row["sales_invoice_item"] for row in request["items"]], [first])
		self.assertEqual(request["total_amount"], 200)
		self.assertEqual(frappe.db.get_value(DOCTYPE, request["name"], "requested_by"), self.user)

	def test_more_than_was_invoiced_is_refused(self):
		"""Nobody can ask for more than the invoice line still has."""
		invoice = self.make_invoice()

		with self.assertRaisesRegex(frappe.ValidationError, "at most 5"):
			self.ask(invoice, {invoice.items[0].name: 6})

	def test_an_invoice_already_fully_credited_is_refused(self):
		"""ERPNext credit notes already raised against the invoice count against what can be asked for."""
		invoice = self.make_invoice()
		self.credit_directly(invoice, {row.name: row.qty for row in invoice.items})

		with self.assertRaisesRegex(frappe.ValidationError, "already been fully credited"):
			self.ask(invoice, {invoice.items[0].name: 1})

		with self.set_user(self.user):
			self.assertNotIn(
				invoice.name, [row["name"] for row in get_creditable_invoices(self.customer).data]
			)
			self.assertFalse(get_sales_invoice(invoice.name)["credit_request"]["can_request"])

	def test_a_partly_credited_line_only_offers_what_is_left(self):
		"""After a credit note for 3 of 5, the form offers 2 and refuses 3."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		self.credit_directly(invoice, {first: 3})

		with self.set_user(self.user):
			form = get_credit_form(self.customer, sales_invoice=invoice.name).data
		line = next(line for line in form["lines"] if line["sales_invoice_item"] == first)
		self.assertEqual((line["credited_qty"], line["available_qty"]), (3, 2))

		with self.assertRaisesRegex(frappe.ValidationError, "at most 2"):
			self.ask(invoice, {first: 3})
		self.assertEqual(self.ask(invoice, {first: 2})["status"], "Pending Review")

	def test_only_one_open_request_per_invoice(self):
		"""A second request waits until the first is decided; a rejection frees the invoice again."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		request = self.ask(invoice, {first: 1})

		with self.assertRaisesRegex(frappe.ValidationError, "still pending review"):
			self.ask(invoice, {first: 1})

		with self.set_user(self.user):
			response = get_credit_form(self.customer, sales_invoice=invoice.name)
		self.assertFalse(response.ok)
		self.assertEqual(response.data["open_request"], request["name"])

		self.review(request["name"], "reject", reason="Goods were fine on delivery")
		self.assertEqual(self.ask(invoice, {first: 1})["status"], "Pending Review")

	def test_another_customers_invoice_cannot_be_credited(self):
		"""The portal only lets a customer ask about their own invoices."""
		other_customer, _user = self.make_customer()
		invoice = self.make_invoice(customer=other_customer)

		with self.assertRaises(frappe.PermissionError):
			self.ask(invoice, {invoice.items[0].name: 1})

	def test_requests_are_off_unless_settings_allow_them(self):
		"""The portal cannot raise requests until Sourcing Settings switches them on."""
		frappe.db.set_single_value(SETTINGS, "allow_customer_credit_requests", 0)
		invoice = self.make_invoice()

		with self.assertRaises(frappe.PermissionError):
			self.ask(invoice, {invoice.items[0].name: 1})

		with self.set_user(self.user):
			self.assertFalse(get_sales_invoice(invoice.name)["credit_request"]["can_request"])

	def test_only_an_accounts_manager_can_approve(self):
		"""Sales staff can see a request but cannot approve it."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 1})
		sales_user = make_test_user(["Sales User"], first_name="Sales").name

		with self.set_user(sales_user), self.assertRaises(frappe.PermissionError):
			frappe.get_doc(DOCTYPE, request["name"]).approve()

	def test_approving_then_creating_the_credit_note(self):
		"""The credit note carries only the approved lines, and its submission closes the request."""
		invoice = self.make_invoice()
		first, second = (row.name for row in invoice.items)
		request = self.ask(invoice, {first: 2, second: 1})

		with self.assertRaisesRegex(frappe.ValidationError, "Only an approved"):
			make_credit_note(request["name"])

		self.assertEqual(self.review(request["name"], "approve").request_status, "Approved")

		credit_note = self.issue(request["name"])
		self.assertEqual(credit_note.return_against, invoice.name)
		self.assertEqual(credit_note.credit_note_request, request["name"])
		self.assertEqual(
			sorted((row.sales_invoice_item, row.qty) for row in credit_note.items),
			sorted([(first, -2), (second, -1)]),
		)
		self.assertEqual(credit_note.total, -240)

		issued = frappe.get_doc(DOCTYPE, request["name"])
		self.assertEqual(
			(issued.request_status, issued.credit_note), ("Credit Note Issued", credit_note.name)
		)

		with self.set_user(self.user):
			view = get_credit_request(request["name"]).data
		self.assertEqual(view["credit_note"]["name"], credit_note.name)

		with self.set_user(self.approver):
			credit_note.reload()
			credit_note.cancel()
		reopened = frappe.get_doc(DOCTYPE, request["name"])
		self.assertEqual((reopened.request_status, reopened.credit_note), ("Approved", None))

	def test_a_second_draft_credit_note_is_refused(self):
		"""Create > Credit Note sends you to the existing draft rather than making another."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 1})
		self.review(request["name"], "approve")

		with self.set_user(self.approver):
			make_credit_note(request["name"]).insert()
			with self.assertRaisesRegex(frappe.ValidationError, "already exists"):
				make_credit_note(request["name"])

	def test_a_credit_note_for_an_unapproved_request_cannot_be_submitted(self):
		"""Linking a credit note to a request does not get round the approval."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 1})
		self.review(request["name"], "approve")

		with self.set_user(self.approver):
			credit_note = make_credit_note(request["name"]).insert()
		frappe.db.set_value(DOCTYPE, request["name"], "request_status", "Pending Review")

		with self.set_user(self.approver), self.assertRaisesRegex(frappe.ValidationError, "pending review"):
			credit_note.submit()

	def test_approval_rechecks_credit_raised_meanwhile(self):
		"""A credit note raised straight on the desk after the request stops an approval that would over-credit."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		request = self.ask(invoice, {first: 4})
		self.credit_directly(invoice, {first: 3})

		with self.assertRaisesRegex(frappe.ValidationError, "at most 2"):
			self.review(request["name"], "approve")

	def test_a_returned_request_is_corrected_and_resubmitted(self):
		"""The customer changes the quantities the reviewer asked about and sends it back for review."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		request = self.ask(invoice, {first: 5})
		self.review(request["name"], "return_for_correction", reason="Only 2 were damaged")

		with self.set_user(self.user):
			form = get_credit_form(self.customer, name=request["name"]).data
			self.assertEqual(form["request"]["review_remarks"], "Only 2 were damaged")
			resubmitted = resubmit_credit_request(
				customer=self.customer,
				name=request["name"],
				items=[{"sales_invoice_item": first, "qty": 2}],
				reason="Damaged Goods",
			).data

		self.assertEqual(resubmitted["status"], "Pending Review")
		self.assertEqual(resubmitted["total_amount"], 200)
		self.assertIsNone(resubmitted["review_remarks"])

	def test_a_pending_request_cannot_be_edited_from_the_portal(self):
		"""Only a request sent back for changes can be resubmitted."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 1})

		with self.set_user(self.user), self.assertRaisesRegex(frappe.ValidationError, "sent back"):
			resubmit_credit_request(
				customer=self.customer,
				name=request["name"],
				items=[{"sales_invoice_item": invoice.items[0].name, "qty": 2}],
				reason="Damaged Goods",
			)

	def test_a_customer_can_withdraw_a_request_under_review(self):
		"""Withdrawing frees the invoice for a fresh request; a decided request stays put."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		request = self.ask(invoice, {first: 1})

		with self.set_user(self.user):
			withdrawn = withdraw_credit_request(self.customer, request["name"]).data
		self.assertEqual(withdrawn["status"], "Withdrawn")

		again = self.ask(invoice, {first: 1})
		self.review(again["name"], "approve")
		with self.set_user(self.user), self.assertRaisesRegex(frappe.ValidationError, "decided"):
			withdraw_credit_request(self.customer, again["name"])

		with self.set_user(self.user):
			statuses = {row["name"]: row["status"] for row in get_credit_requests().data["rows"]}
		self.assertEqual(statuses, {request["name"]: "Withdrawn", again["name"]: "Approved"})

	def test_cancelling_on_the_desk_is_not_shown_as_a_withdrawal(self):
		"""A desk cancel reads Cancelled, so the customer is not told they withdrew it."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 1})

		with self.set_user(self.approver):
			frappe.get_doc(DOCTYPE, request["name"]).cancel()

		with self.set_user(self.user):
			self.assertEqual(get_credit_request(request["name"]).data["status"], "Cancelled")

	def test_a_request_with_a_credit_note_cannot_be_cancelled(self):
		"""Cancelling names the linked credit note so the user can open it."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 1})
		self.review(request["name"], "approve")

		with self.set_user(self.approver):
			draft = make_credit_note(request["name"]).insert()
			with self.assertRaisesRegex(frappe.ValidationError, f"{draft.name}.*Draft"):
				frappe.get_doc(DOCTYPE, request["name"]).cancel()

	def test_a_reviewer_can_lower_quantities_before_approving(self):
		"""Accounts can trim a pending request on the desk; once approved it is locked."""
		invoice = self.make_invoice()
		first, second = (row.name for row in invoice.items)
		request = self.ask(invoice, {first: 4, second: 2})

		with self.set_user(self.approver):
			doc = frappe.get_doc(DOCTYPE, request["name"])
			doc.items[0].qty = 1
			doc.items[1].qty = 0
			doc.save()
		trimmed = frappe.get_doc(DOCTYPE, request["name"])
		self.assertEqual([(row.sales_invoice_item, row.qty) for row in trimmed.items], [(first, 1)])
		self.assertEqual(trimmed.total_amount, 100)

		approved = self.review(request["name"], "approve")
		with (
			self.set_user(self.approver),
			self.assertRaisesRegex(frappe.ValidationError, "no longer be changed"),
		):
			approved.items[0].qty = 2
			approved.save()

	def test_other_needs_a_description(self):
		"""Choosing Other means saying what went wrong."""
		invoice = self.make_invoice()

		with self.assertRaisesRegex(frappe.ValidationError, "Describe what went wrong"):
			self.ask(invoice, {invoice.items[0].name: 1}, reason="Other")

	def test_the_invoice_page_offers_a_request_and_then_links_it(self):
		"""The portal invoice shows the button until a request is open, then points at that request."""
		invoice = self.make_invoice()

		with self.set_user(self.user):
			before = get_sales_invoice(invoice.name)["credit_request"]
		self.assertEqual(before, {"can_request": True, "open_request": None})

		request = self.ask(invoice, {invoice.items[0].name: 1})
		with self.set_user(self.user):
			after = get_sales_invoice(invoice.name)["credit_request"]
		self.assertFalse(after["can_request"])
		self.assertEqual(after["open_request"]["name"], request["name"])
