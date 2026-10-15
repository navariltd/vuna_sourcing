# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, now_datetime, nowdate

from vuna_sourcing.api.transactions.award import (
	close_without_award,
	get_award_overview,
	live_orders_of,
	refresh_pending_selection,
)
from vuna_sourcing.api.transactions.supplier import get_rfq, get_rfqs, send_quote
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures

RFQ = "Request for Quotation"
AWARD = "RFQ Award"


class TestRFQAward(SourcingFixtures, IntegrationTestCase):
	"""One supplier wins the whole request, once bidding is over and the quotations are submitted."""

	def setUp(self):
		super().setUp()
		self.orders_on_award(False)
		self.sent = []
		mailer = patch.object(frappe, "sendmail", side_effect=lambda **email: self.sent.append(email))
		mailer.start()
		self.addCleanup(mailer.stop)

	def orders_on_award(self, enabled):
		frappe.db.set_single_value("Sourcing Settings", "create_purchase_orders_on_award", int(enabled))

	def quote(self, rfq, user, rate):
		with self.set_user(user):
			detail = send_quote(
				rfq.name, items=self.lines(get_rfq(rfq.name), rate=rate), valid_till=add_days(nowdate(), 30)
			)
		return detail["quote"]["name"]

	def submit_quote(self, name):
		quote = frappe.get_doc("Supplier Quotation", name)
		quote.flags.ignore_permissions = True
		quote.submit()
		return quote

	def sealed_rfq_with_quotes(self, *rates, bidding_method="Sealed Bid"):
		bidders = [self.make_supplier() for _ in rates]
		for _, user in bidders:
			frappe.db.set_value("User", user, "enabled", 1)
		rfq = self.make_rfq([supplier for supplier, _ in bidders], bidding_method=bidding_method)
		quotes = [self.quote(rfq, user, rate) for (_, user), rate in zip(bidders, rates, strict=True)]
		return rfq, bidders, quotes

	def ready_rfq(self, *rates, bidding_method="Sealed Bid"):
		rfq, bidders, quotes = self.sealed_rfq_with_quotes(*rates, bidding_method=bidding_method)
		self.close_bids(rfq)
		if bidding_method == "Sealed Bid":
			self.open_bids(rfq)
		for quote in quotes:
			self.submit_quote(quote)
		return rfq, bidders, quotes

	def award(self, rfq, quote, **fields):
		return frappe.get_doc(
			{"doctype": AWARD, "request_for_quotation": rfq.name, "supplier_quotation": quote, **fields}
		).insert()

	def award_status(self, rfq):
		return frappe.db.get_value(RFQ, rfq.name, "award_status")

	def outcomes(self, rfq):
		return dict(
			frappe.get_all(
				"Request for Quotation Supplier",
				filters={"parent": rfq.name},
				fields=["supplier", "award_outcome"],
				as_list=True,
			)
		)

	def emails(self, rfq, phrase):
		return [
			email
			for email in self.sent
			if email.get("reference_name") == rfq.name and phrase in email.get("message", "")
		]

	def test_a_sealed_bid_waits_for_closing_opening_and_a_submitted_quotation(self):
		rfq, _, quotes = self.sealed_rfq_with_quotes(100)
		self.assertFalse(self.award_status(rfq))

		self.close_bids(rfq)
		self.open_bids(rfq)
		self.assertIn("submitted", " ".join(get_award_overview(rfq.name).data["blockers"]))

		self.submit_quote(quotes[0])
		self.assertEqual(self.award_status(rfq), "Pending Selection")

	def test_a_sealed_bid_opened_early_is_ready_only_after_bids_close(self):
		rfq, _, quotes = self.sealed_rfq_with_quotes(100)
		self.open_bids(rfq)
		self.submit_quote(quotes[0])
		self.assertFalse(self.award_status(rfq), "the closing time still has to pass")

		self.close_bids(rfq)
		refresh_pending_selection()
		self.assertEqual(self.award_status(rfq), "Pending Selection")

	def test_a_sealed_bid_opened_below_the_minimum_can_still_be_awarded(self):
		bidder, user = self.make_supplier()
		rfq = self.make_rfq([bidder], minimum_expected_quotes=3)
		quote = self.quote(rfq, user, 100)
		self.close_bids(rfq)
		self.open_bids(rfq)
		self.submit_quote(quote)

		self.award(rfq, quote).submit()
		self.assertEqual(self.award_status(rfq), "Awarded")

	def test_an_open_bid_is_ready_once_bids_close_and_a_quotation_is_submitted(self):
		rfq, _, _ = self.ready_rfq(100, bidding_method="Open Bid")
		self.assertEqual(self.award_status(rfq), "Pending Selection")

	def test_the_award_cannot_be_made_before_the_request_is_ready(self):
		rfq, _, quotes = self.sealed_rfq_with_quotes(100)
		self.assertRaises(frappe.ValidationError, self.award, rfq, quotes[0])

	def test_awarding_the_lowest_marks_the_winner_and_tells_everyone(self):
		rfq, bidders, quotes = self.ready_rfq(120, 90)
		(dear, _), (cheap, _) = bidders

		award = self.award(rfq, quotes[1])
		self.assertTrue(award.is_lowest)
		self.assertEqual((award.supplier, award.rank, award.total), (cheap, 1, 450))
		award.submit()

		rfq.reload()
		self.assertEqual(rfq.award_status, "Awarded")
		self.assertEqual(self.outcomes(rfq), {cheap: "Awarded", dear: "Not Selected"})
		self.assertEqual(frappe.db.get_value("Supplier Quotation", quotes[1], "award_outcome"), "Awarded")
		self.assertEqual(
			frappe.db.get_value("Supplier Quotation", quotes[0], "award_outcome"), "Not Selected"
		)
		self.assertTrue(self.emails(rfq, "has been selected"))
		self.assertTrue(self.emails(rfq, "was not selected"))

	def test_a_supplier_who_declined_gets_no_outcome(self):
		rfq, _, quotes = self.sealed_rfq_with_quotes(100)
		silent, _ = self.make_supplier()
		rfq.append("suppliers", {"supplier": silent, "send_email": 0})
		rfq.flags.ignore_validate_update_after_submit = True
		rfq.save(ignore_permissions=True)
		self.close_bids(rfq)
		self.open_bids(rfq)
		self.submit_quote(quotes[0])

		self.award(rfq, quotes[0]).submit()
		self.assertIsNone(self.outcomes(rfq)[silent])

	def test_a_higher_quotation_needs_a_justification(self):
		rfq, _, quotes = self.ready_rfq(120, 90)

		self.assertRaisesRegex(frappe.ValidationError, "Justification", self.award, rfq, quotes[0])
		award = self.award(rfq, quotes[0], justification="Faster delivery and proven quality.")
		self.assertEqual((award.rank, award.is_lowest), (2, 0))

	def test_a_request_is_awarded_only_once(self):
		rfq, _, quotes = self.ready_rfq(120, 90)
		self.award(rfq, quotes[1]).submit()

		self.assertRaises(
			frappe.ValidationError, self.award, rfq, quotes[0], justification="Second thoughts."
		)

	def test_only_a_submitted_quotation_for_the_request_can_win(self):
		rfq, _, _ = self.ready_rfq(100)
		_, _, other_quotes = self.ready_rfq(90)

		self.assertRaisesRegex(
			frappe.ValidationError, "not a submitted quotation", self.award, rfq, other_quotes[0]
		)

	def test_the_setting_drafts_a_purchase_order_and_cancelling_removes_it(self):
		self.orders_on_award(True)
		rfq, bidders, quotes = self.ready_rfq(100)

		award = self.award(rfq, quotes[0])
		award.submit()

		order = frappe.get_doc("Purchase Order", live_orders_of(award.name)[0])
		self.assertEqual((order.docstatus, order.supplier, order.rfq_award), (0, bidders[0][0], award.name))
		self.assertEqual([row.supplier_quotation for row in order.items], [quotes[0]])

		award.cancel()
		self.assertFalse(frappe.db.exists("Purchase Order", order.name))
		self.assertEqual(self.award_status(rfq), "Pending Selection")
		self.assertEqual(set(self.outcomes(rfq).values()), {None})
		self.assertTrue(self.emails(rfq, "has been withdrawn"))

	def test_a_submitted_purchase_order_blocks_cancelling_the_award(self):
		self.orders_on_award(True)
		rfq, _, quotes = self.ready_rfq(100)
		award = self.award(rfq, quotes[0])
		award.submit()

		order = frappe.get_doc("Purchase Order", live_orders_of(award.name)[0])
		order.submit()

		award.reload()
		self.assertRaisesRegex(frappe.ValidationError, "before cancelling", award.cancel)

	def test_without_the_setting_the_purchase_order_is_created_on_request_once(self):
		rfq, _, quotes = self.ready_rfq(100)
		award = self.award(rfq, quotes[0])
		award.submit()
		self.assertFalse(live_orders_of(award.name))

		response = award.create_purchase_order()
		self.assertTrue(response.ok)
		self.assertEqual(live_orders_of(award.name), [response.data["purchase_order"]])
		self.assertRaises(frappe.ValidationError, award.create_purchase_order)

	def test_the_purchase_order_is_never_required_before_today(self):
		rfq, _, quotes = self.ready_rfq(100)
		rfq.db_set("schedule_date", None)
		for row in rfq.items:
			row.db_set("schedule_date", add_days(nowdate(), -10))
		award = self.award(rfq, quotes[0])
		award.submit()

		order = frappe.get_doc("Purchase Order", award.create_purchase_order().data["purchase_order"])

		self.assertEqual(str(order.schedule_date), nowdate())
		self.assertEqual({str(row.schedule_date) for row in order.items}, {nowdate()})

	def test_the_purchase_order_keeps_a_future_rfq_date(self):
		rfq, _, quotes = self.ready_rfq(100)
		due = add_days(nowdate(), 20)
		for row in rfq.items:
			row.db_set("schedule_date", due)
		award = self.award(rfq, quotes[0])
		award.submit()

		order = frappe.get_doc("Purchase Order", award.create_purchase_order().data["purchase_order"])
		self.assertEqual({str(row.schedule_date) for row in order.items}, {due})

	def test_cancelling_the_award_leaves_the_request_and_quotations_submitted(self):
		rfq, _, quotes = self.ready_rfq(120, 90)
		award = self.award(rfq, quotes[1])
		award.submit()
		award.cancel()

		self.assertEqual(frappe.db.get_value(RFQ, rfq.name, "docstatus"), 1)
		self.assertEqual(
			set(frappe.get_all("Supplier Quotation", filters={"name": ("in", quotes)}, pluck="docstatus")),
			{1},
		)

	def test_a_submitted_purchase_order_cancels_on_its_own_and_the_award_stays(self):
		from frappe.desk.form.linked_with import get_submitted_linked_docs

		rfq, _, quotes = self.ready_rfq(120, 90)
		award = self.award(rfq, quotes[1])
		award.submit()
		order = frappe.get_doc("Purchase Order", award.create_purchase_order().data["purchase_order"])
		order.submit()

		linked = {row["doctype"] for row in get_submitted_linked_docs("Purchase Order", order.name)["docs"]}
		self.assertFalse(linked & {AWARD, RFQ, "Supplier Quotation"})

		order.cancel()
		self.assertEqual(frappe.db.get_value(AWARD, award.name, "docstatus"), 1)
		self.assertEqual(self.award_status(rfq), "Awarded")
		self.assertFalse(live_orders_of(award.name))
		self.assertTrue(award.create_purchase_order().ok, "a fresh order can replace the cancelled one")

	def test_cancelling_without_orders_reopens_the_decision(self):
		rfq, _, quotes = self.ready_rfq(100)
		award = self.award(rfq, quotes[0])
		award.submit()
		award.cancel()

		self.assertEqual(self.award_status(rfq), "Pending Selection")
		self.award(rfq, quotes[0]).submit()
		self.assertEqual(self.award_status(rfq), "Awarded")

	def test_closing_without_an_award_tells_everyone_they_were_not_selected(self):
		rfq, _, quotes = self.ready_rfq(120, 90)

		response = close_without_award(rfq.name, "Budget withdrawn.")

		self.assertEqual(response.data["award_status"], "Not Awarded")
		self.assertEqual(set(self.outcomes(rfq).values()), {"Not Selected"})
		self.assertEqual(frappe.db.get_value(RFQ, rfq.name, "award_remarks"), "Budget withdrawn.")
		self.assertTrue(self.emails(rfq, "was not selected"))
		self.assertRaises(frappe.ValidationError, self.award, rfq, quotes[1])

	def test_only_a_request_pending_selection_can_be_closed_without_an_award(self):
		rfq, _, _ = self.sealed_rfq_with_quotes(100)
		self.assertRaises(frappe.ValidationError, close_without_award, rfq.name, "Too early.")

	def test_the_supplier_portal_shows_the_outcome_without_the_rank(self):
		rfq, bidders, quotes = self.ready_rfq(120, 90)
		(_, loser), (_, winner) = bidders
		self.award(rfq, quotes[1]).submit()

		with self.set_user(winner):
			self.assertEqual(get_rfq(rfq.name)["status"], "Awarded")
			self.assertEqual(get_rfqs(status="Awarded")["counts"].get("Awarded"), 1)
		with self.set_user(loser):
			detail = get_rfq(rfq.name)
		self.assertEqual(detail["status"], "Not Selected")
		self.assertNotIn("rank", frappe.as_json(detail))

	def test_suppliers_and_buyers_without_award_rights_cannot_decide(self):
		rfq, bidders, _ = self.ready_rfq(100)
		clerk = make_test_user(["Purchase User"], first_name="Clerk").name

		with self.set_user(bidders[0][1]):
			self.assertRaises(frappe.PermissionError, get_award_overview, rfq.name)
		with self.set_user(clerk):
			self.assertRaises(frappe.PermissionError, close_without_award, rfq.name, "No.")

	def test_the_overview_ranks_quotations_by_total(self):
		rfq, _, quotes = self.ready_rfq(120, 90, 100)

		overview = get_award_overview(rfq.name).data
		self.assertEqual(
			[quote["supplier_quotation"] for quote in overview["quotes"]], [quotes[1], quotes[2], quotes[0]]
		)
		self.assertEqual([quote["is_lowest"] for quote in overview["quotes"]], [True, False, False])
		self.assertEqual(overview["blockers"], [])

	def test_the_hourly_refresh_leaves_requests_still_bidding_alone(self):
		rfq, _, _ = self.sealed_rfq_with_quotes(100)
		rfq.db_set("bid_closing", add_to_date(now_datetime(), hours=2))
		refresh_pending_selection()
		self.assertFalse(self.award_status(rfq))
