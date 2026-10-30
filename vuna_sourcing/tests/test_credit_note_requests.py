# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.accounts.utils import get_balance_on
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
REASON = "Charged More Than Agreed"


class TestCreditNoteRequests(SourcingFixtures, IntegrationTestCase):
	"""Customers asking for lower prices on an invoice, and Accounts approving them on the desk."""

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

	def vat_account(self):
		account = frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Tax", "is_group": 0}, "name"
		)
		if account:
			return account

		parent = frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Liability", "is_group": 1}, "name"
		)
		return (
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "_Test Credit Request VAT",
					"company": self.company,
					"parent_account": parent,
					"account_type": "Tax",
					"tax_rate": 16,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def owed(self):
		return get_balance_on(party_type="Customer", party=self.customer, company=self.company)

	def make_invoice(self, customer=None, lines=((5, 100), (3, 40)), vat=False):
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
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": self.vat_account(),
						"description": "VAT",
						"rate": 16,
					}
				]
				if vat
				else [],
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

	def ask(self, invoice, price_by_row, reason=REASON, description=None):
		with self.set_user(self.user):
			return submit_credit_request(
				customer=self.customer,
				sales_invoice=invoice.name,
				items=[{"sales_invoice_item": row, "new_rate": price} for row, price in price_by_row.items()],
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

	def test_a_customer_asks_for_a_lower_price_on_part_of_an_invoice(self):
		"""Only the lowered lines are kept, covering every invoiced unit, and the request waits for review."""
		invoice = self.make_invoice()
		first, second = (row.name for row in invoice.items)

		request = self.ask(invoice, {first: 80, second: 40})

		self.assertEqual(request["status"], "Pending Review")
		self.assertEqual(
			[
				(row["sales_invoice_item"], row["qty"], row["new_rate"], row["discount_percentage"])
				for row in request["items"]
			],
			[(first, 5, 80, 20)],
		)
		self.assertEqual(request["total_amount"], 100)
		self.assertEqual(frappe.db.get_value(DOCTYPE, request["name"], "requested_by"), self.user)

	def test_the_percentage_off_is_worked_out_on_the_server(self):
		"""Whatever the portal shows, the stored percentage and amount come from the new price."""
		invoice = self.make_invoice()

		request = self.ask(invoice, {invoice.items[1].name: 30})

		self.assertEqual(request["items"][0]["discount_percentage"], 25)
		self.assertEqual(request["total_amount"], 30)

	def test_a_price_above_the_invoiced_price_is_refused(self):
		"""An adjustment can only lower a price."""
		invoice = self.make_invoice()

		with self.assertRaisesRegex(frappe.ValidationError, "must be lower than its invoiced price"):
			self.ask(invoice, {invoice.items[0].name: 120})

	def test_a_negative_or_missing_price_is_refused(self):
		"""A line sent without a new price is never read as free."""
		invoice = self.make_invoice()
		first = invoice.items[0].name

		with self.assertRaisesRegex(frappe.ValidationError, "zero or more"):
			self.ask(invoice, {first: -1})

		with self.set_user(self.user), self.assertRaisesRegex(frappe.ValidationError, "Enter a new price"):
			submit_credit_request(
				customer=self.customer,
				sales_invoice=invoice.name,
				items=[{"sales_invoice_item": first}],
				reason=REASON,
			)

	def test_a_request_must_lower_something(self):
		"""Sending every price unchanged is refused."""
		invoice = self.make_invoice()

		with self.assertRaisesRegex(frappe.ValidationError, "Lower the price of at least one item"):
			self.ask(invoice, {invoice.items[0].name: 100})

	def test_a_request_needs_a_reason_from_the_list(self):
		"""No reason, or one that is not offered, is refused; Other also needs details."""
		invoice = self.make_invoice()
		first = invoice.items[0].name

		with self.assertRaisesRegex(frappe.ValidationError, "Choose why"):
			self.ask(invoice, {first: 80}, reason=None)

		with self.assertRaisesRegex(frappe.ValidationError, "not one of the reasons"):
			self.ask(invoice, {first: 80}, reason="Damaged Goods")

		with self.assertRaisesRegex(frappe.ValidationError, "Describe why"):
			self.ask(invoice, {first: 80}, reason="Other")

		self.assertEqual(
			self.ask(invoice, {first: 80}, reason="Other", description="Promised at 80 on the phone")[
				"status"
			],
			"Pending Review",
		)

	def test_an_invoice_already_fully_credited_is_refused(self):
		"""ERPNext credit notes already raised against the invoice leave nothing to adjust."""
		invoice = self.make_invoice()
		self.credit_directly(invoice, {row.name: row.qty for row in invoice.items})

		with self.assertRaisesRegex(frappe.ValidationError, "already been fully credited"):
			self.ask(invoice, {invoice.items[0].name: 80})

		with self.set_user(self.user):
			self.assertNotIn(
				invoice.name, [row["name"] for row in get_creditable_invoices(self.customer).data]
			)
			self.assertFalse(get_sales_invoice(invoice.name)["credit_request"]["can_request"])

	def test_a_partly_credited_line_only_adjusts_the_units_left(self):
		"""After a credit note for 3 of 5, the new price applies to the other 2."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		self.credit_directly(invoice, {first: 3})

		with self.set_user(self.user):
			form = get_credit_form(self.customer, sales_invoice=invoice.name).data
		line = next(line for line in form["lines"] if line["sales_invoice_item"] == first)
		self.assertEqual((line["available_qty"], line["new_rate"]), (2, 100))

		request = self.ask(invoice, {first: 80})
		self.assertEqual((request["items"][0]["qty"], request["total_amount"]), (2, 40))

	def test_only_one_open_request_per_invoice(self):
		"""A second request waits until the first is decided; a rejection frees the invoice again."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		request = self.ask(invoice, {first: 90})

		with self.assertRaisesRegex(frappe.ValidationError, "still pending review"):
			self.ask(invoice, {first: 90})

		with self.set_user(self.user):
			response = get_credit_form(self.customer, sales_invoice=invoice.name)
		self.assertFalse(response.ok)
		self.assertEqual(response.data["open_request"], request["name"])

		self.review(request["name"], "reject", reason="The invoiced price is the agreed one")
		self.assertEqual(self.ask(invoice, {first: 90})["status"], "Pending Review")

	def test_another_customers_invoice_cannot_be_adjusted(self):
		"""The portal only lets a customer ask about their own invoices."""
		other_customer, _user = self.make_customer()
		invoice = self.make_invoice(customer=other_customer)

		with self.assertRaises(frappe.PermissionError):
			self.ask(invoice, {invoice.items[0].name: 80})

	def test_requests_are_off_unless_settings_allow_them(self):
		"""The portal cannot raise or resubmit requests until Sourcing Settings switches them on."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		request = self.ask(invoice, {first: 80})
		self.review(request["name"], "return_for_correction", reason="Check the price")

		frappe.db.set_single_value(SETTINGS, "allow_customer_credit_requests", 0)
		other = self.make_invoice()

		with self.assertRaises(frappe.PermissionError):
			self.ask(other, {other.items[0].name: 80})

		with self.set_user(self.user):
			with self.assertRaises(frappe.PermissionError):
				resubmit_credit_request(
					customer=self.customer,
					name=request["name"],
					items=[{"sales_invoice_item": first, "new_rate": 90}],
					reason=REASON,
				)
			with self.assertRaises(frappe.PermissionError):
				get_creditable_invoices(self.customer)
			self.assertFalse(get_sales_invoice(other.name)["credit_request"]["can_request"])
			self.assertFalse(get_credit_request(request["name"]).data["editable"])

	def test_only_an_accounts_manager_can_approve(self):
		"""Sales staff can see a request but cannot approve it."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 80})
		sales_user = make_test_user(["Sales User"], first_name="Sales").name

		with self.set_user(sales_user), self.assertRaises(frappe.PermissionError):
			frappe.get_doc(DOCTYPE, request["name"]).approve()

	def test_approving_then_creating_the_credit_note(self):
		"""The credit note credits the price difference on each unit, leaves stock alone, and closes the request."""
		invoice = self.make_invoice()
		first, second = (row.name for row in invoice.items)
		request = self.ask(invoice, {first: 80, second: 30})

		with self.assertRaisesRegex(frappe.ValidationError, "Only an approved"):
			make_credit_note(request["name"])

		self.assertEqual(self.review(request["name"], "approve").request_status, "Approved")

		credit_note = self.issue(request["name"])
		self.assertEqual(credit_note.return_against, invoice.name)
		self.assertEqual(credit_note.credit_note_request, request["name"])
		self.assertFalse(credit_note.update_stock)
		self.assertEqual(
			sorted((row.sales_invoice_item, row.qty, row.rate) for row in credit_note.items),
			sorted([(first, -5, 20), (second, -3, 10)]),
		)
		self.assertEqual(credit_note.total, -130)

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

	def test_the_credit_note_lowers_what_the_customer_owes_by_the_approved_amount(self):
		"""The approved reduction is exactly what comes off the invoice and the customer's receivable."""
		invoice = self.make_invoice()
		first, second = (row.name for row in invoice.items)
		owed_before = self.owed()

		request = self.ask(invoice, {first: 80, second: 30})
		self.review(request["name"], "approve")
		credit_note = self.issue(request["name"])

		self.assertEqual(request["total_amount"], 130)
		self.assertEqual(credit_note.grand_total, -130)
		self.assertEqual(frappe.db.get_value("Sales Invoice", invoice.name, "outstanding_amount"), 490)
		self.assertEqual(owed_before - self.owed(), 130)

		receivable = frappe.get_all(
			"GL Entry",
			filters={"voucher_no": credit_note.name, "account": invoice.debit_to, "is_cancelled": 0},
			fields=["credit", "against_voucher"],
		)
		self.assertEqual([(row.credit, row.against_voucher) for row in receivable], [(130, invoice.name)])

	def test_vat_on_the_reduction_also_comes_off_the_receivable(self):
		"""With 16% VAT, the customer owes the reduction plus its VAT less, and nothing more."""
		invoice = self.make_invoice(vat=True)
		first = invoice.items[0].name
		owed_before = self.owed()
		outstanding_before = invoice.outstanding_amount

		request = self.ask(invoice, {first: 80})
		self.review(request["name"], "approve")
		credit_note = self.issue(request["name"])

		self.assertEqual(request["total_amount"], 100)
		self.assertEqual((credit_note.net_total, credit_note.total_taxes_and_charges), (-100, -16))
		self.assertEqual(credit_note.grand_total, -116)
		self.assertEqual(
			outstanding_before - frappe.db.get_value("Sales Invoice", invoice.name, "outstanding_amount"),
			116,
		)
		self.assertEqual(owed_before - self.owed(), 116)

	def test_cancelling_the_credit_note_restores_what_the_customer_owes(self):
		"""A cancelled credit note puts the receivable back and reopens the approved request."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 80})
		self.review(request["name"], "approve")
		owed_before = self.owed()

		credit_note = self.issue(request["name"])
		self.assertEqual(owed_before - self.owed(), 100)

		with self.set_user(self.approver):
			credit_note.reload()
			credit_note.cancel()
		self.assertEqual(self.owed(), owed_before)
		self.assertEqual(frappe.db.get_value("Sales Invoice", invoice.name, "outstanding_amount"), 620)

	def test_a_second_draft_credit_note_is_refused(self):
		"""Create > Credit Note sends you to the existing draft rather than making another."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 80})
		self.review(request["name"], "approve")

		with self.set_user(self.approver):
			make_credit_note(request["name"]).insert()
			with self.assertRaisesRegex(frappe.ValidationError, "already exists"):
				make_credit_note(request["name"])

	def test_a_credit_note_for_an_unapproved_request_cannot_be_submitted(self):
		"""Linking a credit note to a request does not get round the approval."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 80})
		self.review(request["name"], "approve")

		with self.set_user(self.approver):
			credit_note = make_credit_note(request["name"]).insert()
		frappe.db.set_value(DOCTYPE, request["name"], "request_status", "Pending Review")

		with self.set_user(self.approver), self.assertRaisesRegex(frappe.ValidationError, "pending review"):
			credit_note.submit()

	def test_approval_rechecks_credit_raised_meanwhile(self):
		"""A credit note raised on the desk after the request stops an approval at the old amount."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		request = self.ask(invoice, {first: 80})
		self.credit_directly(invoice, {first: 3})

		with self.assertRaisesRegex(frappe.ValidationError, "Save the request to refresh"):
			self.review(request["name"], "approve")

		with self.set_user(self.approver):
			frappe.get_doc(DOCTYPE, request["name"]).save()
		self.assertEqual(self.review(request["name"], "approve").total_amount, 40)

		later = self.make_invoice()
		request = self.ask(later, {later.items[0].name: 80})
		self.credit_directly(later, {later.items[0].name: 5})
		with self.assertRaisesRegex(frappe.ValidationError, "fully covered by credit notes"):
			self.review(request["name"], "approve")

	def test_a_returned_request_is_corrected_and_resubmitted(self):
		"""The customer changes the price the reviewer asked about and sends it back for review."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		request = self.ask(invoice, {first: 50})
		self.review(request["name"], "return_for_correction", reason="The agreed price was 90")

		with self.set_user(self.user):
			form = get_credit_form(self.customer, name=request["name"]).data
			self.assertEqual(form["request"]["review_remarks"], "The agreed price was 90")
			self.assertEqual(
				next(line["new_rate"] for line in form["lines"] if line["sales_invoice_item"] == first), 50
			)
			resubmitted = resubmit_credit_request(
				customer=self.customer,
				name=request["name"],
				items=[{"sales_invoice_item": first, "new_rate": 90}],
				reason=REASON,
			).data

		self.assertEqual(resubmitted["status"], "Pending Review")
		self.assertEqual(resubmitted["total_amount"], 50)
		self.assertIsNone(resubmitted["review_remarks"])

	def test_a_pending_request_cannot_be_edited_from_the_portal(self):
		"""Only a request sent back for changes can be resubmitted."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 80})

		with self.set_user(self.user), self.assertRaisesRegex(frappe.ValidationError, "sent back"):
			resubmit_credit_request(
				customer=self.customer,
				name=request["name"],
				items=[{"sales_invoice_item": invoice.items[0].name, "new_rate": 70}],
				reason=REASON,
			)

	def test_a_customer_can_withdraw_a_request_under_review(self):
		"""Withdrawing frees the invoice for a fresh request; a decided request stays put."""
		invoice = self.make_invoice()
		first = invoice.items[0].name
		request = self.ask(invoice, {first: 80})

		with self.set_user(self.user):
			withdrawn = withdraw_credit_request(self.customer, request["name"]).data
		self.assertEqual(withdrawn["status"], "Withdrawn")

		again = self.ask(invoice, {first: 80})
		self.review(again["name"], "approve")
		with self.set_user(self.user), self.assertRaisesRegex(frappe.ValidationError, "decided"):
			withdraw_credit_request(self.customer, again["name"])

		with self.set_user(self.user):
			statuses = {row["name"]: row["status"] for row in get_credit_requests().data["rows"]}
		self.assertEqual(statuses, {request["name"]: "Withdrawn", again["name"]: "Approved"})

	def test_cancelling_on_the_desk_is_not_shown_as_a_withdrawal(self):
		"""A desk cancel reads Cancelled, so the customer is not told they withdrew it."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 80})

		with self.set_user(self.approver):
			frappe.get_doc(DOCTYPE, request["name"]).cancel()

		with self.set_user(self.user):
			self.assertEqual(get_credit_request(request["name"]).data["status"], "Cancelled")

	def test_a_request_with_a_credit_note_cannot_be_cancelled(self):
		"""Cancelling names the linked credit note so the user can open it."""
		invoice = self.make_invoice()
		request = self.ask(invoice, {invoice.items[0].name: 80})
		self.review(request["name"], "approve")

		with self.set_user(self.approver):
			draft = make_credit_note(request["name"]).insert()
			with self.assertRaisesRegex(frappe.ValidationError, f"{draft.name}.*Draft"):
				frappe.get_doc(DOCTYPE, request["name"]).cancel()

	def test_a_reviewer_can_change_prices_before_approving(self):
		"""Accounts can adjust a pending request on the desk; once approved it is locked."""
		invoice = self.make_invoice()
		first, second = (row.name for row in invoice.items)
		request = self.ask(invoice, {first: 60, second: 30})

		with self.set_user(self.approver):
			doc = frappe.get_doc(DOCTYPE, request["name"])
			doc.items[0].new_rate = 90
			doc.items[1].new_rate = 40
			doc.save()
		trimmed = frappe.get_doc(DOCTYPE, request["name"])
		self.assertEqual(
			[(row.sales_invoice_item, row.new_rate, row.discount_percentage) for row in trimmed.items],
			[(first, 90, 10)],
		)
		self.assertEqual(trimmed.total_amount, 50)

		approved = self.review(request["name"], "approve")
		with (
			self.set_user(self.approver),
			self.assertRaisesRegex(frappe.ValidationError, "no longer be changed"),
		):
			approved.items[0].new_rate = 70
			approved.save()

	def test_the_invoice_page_offers_a_request_and_then_links_it(self):
		"""The portal invoice shows the button until a request is open, then points at that request."""
		invoice = self.make_invoice()

		with self.set_user(self.user):
			before = get_sales_invoice(invoice.name)["credit_request"]
		self.assertEqual(before, {"can_request": True, "open_request": None})

		request = self.ask(invoice, {invoice.items[0].name: 80})
		with self.set_user(self.user):
			after = get_sales_invoice(invoice.name)["credit_request"]
		self.assertFalse(after["can_request"])
		self.assertEqual(after["open_request"]["name"], request["name"])
