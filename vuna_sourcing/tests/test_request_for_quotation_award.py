# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, getdate, now_datetime, nowdate

from vuna_sourcing.api.transactions.award import (
	close_remaining_items,
	get_award_overview,
	get_item_bids,
	make_purchase_order,
	quotation_query,
	refresh_pending_selection,
)
from vuna_sourcing.api.transactions.supplier import get_rfq, get_rfqs, send_quote
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures

RFQ = "Request for Quotation"
AWARD = "Request for Quotation Award"
SECOND_ITEM = "_Test Portal RFQ Item 2"


class TestRequestForQuotationAward(SourcingFixtures, IntegrationTestCase):
	"""An RFQ is awarded in full to one supplier, or item by item across suppliers."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Item", SECOND_ITEM):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": SECOND_ITEM,
					"item_name": SECOND_ITEM,
					"description": SECOND_ITEM,
					"item_group": frappe.db.get_value("Item", cls.item, "item_group"),
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()

	def setUp(self):
		super().setUp()
		self.sent = []
		mailer = patch.object(frappe, "sendmail", side_effect=lambda **email: self.sent.append(email))
		mailer.start()
		self.addCleanup(mailer.stop)
		self.orders_on_award(False)

	def orders_on_award(self, enabled):
		frappe.db.set_single_value("Sourcing Settings", "create_purchase_orders_on_award", int(enabled))

	def drafted_orders(self, quote):
		return frappe.get_all(
			"Purchase Order Item",
			filters={"supplier_quotation": quote, "docstatus": 0},
			pluck="parent",
			distinct=True,
		)

	def make_two_item_rfq(self, suppliers, bidding_method="Sealed Bid", **fields):
		required_by = add_days(nowdate(), 7)
		doc = frappe.get_doc(
			{
				"doctype": RFQ,
				"company": self.company,
				"transaction_date": nowdate(),
				"schedule_date": required_by,
				"bidding_method": bidding_method,
				"bid_closing": add_to_date(now_datetime(), days=7),
				"opening_committee": self.committee,
				"message_for_supplier": "Please quote your best price.",
				"suppliers": [{"supplier": supplier, "send_email": 0} for supplier in suppliers],
				"items": [
					{
						"item_code": item_code,
						"qty": qty,
						"uom": "Nos",
						"conversion_factor": 1,
						"warehouse": self.warehouse,
						"schedule_date": required_by,
					}
					for item_code, qty in ((self.item, 5), (SECOND_ITEM, 10))
				],
				**fields,
			}
		).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def quote(self, rfq, user, rates):
		with self.set_user(user):
			detail = get_rfq(rfq.name)
			lines = [
				{"rfq_item": item["name"], "rate": rate, "lead_time_days": 3}
				for item, rate in zip(detail["items"], rates, strict=True)
			]
			return send_quote(rfq.name, items=lines, valid_till=add_days(nowdate(), 30))["quote"]["name"]

	def submit_quote(self, name):
		quote = frappe.get_doc("Supplier Quotation", name)
		quote.flags.ignore_permissions = True
		quote.submit()
		return quote

	def bidders(self, count):
		bidders = [self.make_supplier() for _ in range(count)]
		for _, user in bidders:
			frappe.db.set_value("User", user, "enabled", 1)
		return bidders

	def quoted_rfq(self, *price_lists, bidding_method="Sealed Bid", **fields):
		bidders = self.bidders(len(price_lists))
		rfq = self.make_two_item_rfq([supplier for supplier, _ in bidders], bidding_method, **fields)
		quotes = [self.quote(rfq, user, rates) for (_, user), rates in zip(bidders, price_lists, strict=True)]
		return rfq, [supplier for supplier, _ in bidders], quotes

	def open_up(self, rfq, quotes):
		self.close_bids(rfq)
		if rfq.bidding_method == "Sealed Bid":
			self.open_bids(rfq)
		for quote in quotes:
			self.submit_quote(quote)

	def ready_rfq(self, *price_lists, bidding_method="Sealed Bid"):
		rfq, suppliers, quotes = self.quoted_rfq(*price_lists, bidding_method=bidding_method)
		self.open_up(rfq, quotes)
		return rfq, suppliers, quotes

	def standard_rfq(self):
		return self.ready_rfq([100, 40], [80, 60], [120, 70])

	def lines(self, rfq):
		return [row.name for row in frappe.get_doc(RFQ, rfq.name).items]

	def full_award(self, rfq, quote, **fields):
		return frappe.get_doc(
			{
				"doctype": AWARD,
				"request_for_quotation": rfq.name,
				"award_basis": "Full Award",
				"awarded_quotation": quote,
				**fields,
			}
		).insert()

	def partial_award(self, rfq, rows):
		return frappe.get_doc(
			{
				"doctype": AWARD,
				"request_for_quotation": rfq.name,
				"award_basis": "Partial Award",
				"items": [{"request_for_quotation_item": line, **row} for line, row in rows],
			}
		).insert()

	def award_status(self, rfq):
		return frappe.db.get_value(RFQ, rfq.name, "award_status")

	def line_statuses(self, rfq):
		return [row.award_status or None for row in frappe.get_doc(RFQ, rfq.name).items]

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
		rfq, _, quotes = self.quoted_rfq([100, 40])
		self.assertFalse(self.award_status(rfq))

		self.close_bids(rfq)
		self.open_bids(rfq)
		self.assertIn("submitted", " ".join(get_award_overview(rfq.name).data["blockers"]))

		self.submit_quote(quotes[0])
		self.assertEqual(self.award_status(rfq), "Pending Selection")

	def test_a_sealed_bid_opened_early_is_ready_only_after_bids_close(self):
		rfq, _, quotes = self.quoted_rfq([100, 40])
		self.open_bids(rfq)
		self.submit_quote(quotes[0])
		self.assertFalse(self.award_status(rfq))

		self.close_bids(rfq)
		refresh_pending_selection()
		self.assertEqual(self.award_status(rfq), "Pending Selection")

	def test_a_sealed_bid_opened_below_the_minimum_can_still_be_awarded(self):
		rfq, _, quotes = self.quoted_rfq([100, 40], minimum_expected_quotes=3)
		self.open_up(rfq, quotes)

		self.full_award(rfq, quotes[0]).submit()
		self.assertEqual(self.award_status(rfq), "Awarded")

	def test_an_open_bid_is_ready_once_bids_close(self):
		rfq, _, _ = self.ready_rfq([100, 40], bidding_method="Open Bid")
		self.assertEqual(self.award_status(rfq), "Pending Selection")

	def test_the_award_waits_until_the_request_is_ready(self):
		rfq, _, quotes = self.quoted_rfq([100, 40])
		self.assertRaises(frappe.ValidationError, self.full_award, rfq, quotes[0])

	def test_the_overview_summarises_each_item_and_each_complete_quotation(self):
		rfq, _, quotes = self.standard_rfq()

		overview = get_award_overview(rfq.name).data
		first, second = overview["lines"]
		self.assertEqual(overview["supplier_count"], 3)
		self.assertEqual(first["bid_count"], 3)
		self.assertEqual(
			[bid["supplier_quotation"] for bid in first["top_bids"]], [quotes[1], quotes[0], quotes[2]]
		)
		self.assertEqual(second["top_bids"][0]["supplier_quotation"], quotes[0])
		self.assertEqual([quote["supplier_quotation"] for quote in overview["quotes"]], quotes)
		self.assertEqual([quote["base_total"] for quote in overview["quotes"]], [900, 1000, 1300])

	def test_with_many_bidders_only_the_cheapest_bids_ship_with_the_page(self):
		rfq, _, quotes = self.ready_rfq([100, 40], [80, 60], [120, 70], [90, 50], [110, 45])

		first, _ = get_award_overview(rfq.name).data["lines"]
		self.assertEqual(first["bid_count"], 5)
		self.assertEqual(
			[bid["supplier_quotation"] for bid in first["top_bids"]], [quotes[1], quotes[3], quotes[0]]
		)

	def test_an_items_bids_are_ranked_cheapest_first(self):
		rfq, _, quotes = self.standard_rfq()
		_first, second = self.lines(rfq)

		bids = get_item_bids(rfq.name, second).data
		self.assertEqual([bid["supplier_quotation"] for bid in bids], [quotes[0], quotes[1], quotes[2]])
		self.assertEqual([bid["item_rank"] for bid in bids], [1, 2, 3])
		self.assertEqual([bid["is_lowest"] for bid in bids], [True, False, False])

	def test_the_quotation_picker_searches_by_supplier_and_shows_price_and_rank(self):
		rfq, suppliers, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)
		name = frappe.db.get_value("Supplier", suppliers[2], "supplier_name")

		per_item = quotation_query(
			"Supplier Quotation",
			"",
			"name",
			0,
			20,
			{"request_for_quotation": rfq.name, "request_for_quotation_item": first},
		)
		self.assertEqual([option[0] for option in per_item], [quotes[1], quotes[0], quotes[2]])
		self.assertIn("rank 1", per_item[0][2])
		self.assertIn("lowest", per_item[0][2])

		found = quotation_query(
			"Supplier Quotation", name[-6:], "name", 0, 20, {"request_for_quotation": rfq.name}
		)
		self.assertEqual([option[0] for option in found], [quotes[2]])
		self.assertIn("rank 3", found[0][2])

		paged = quotation_query("Supplier Quotation", "", "name", 1, 1, {"request_for_quotation": rfq.name})
		self.assertEqual([option[0] for option in paged], [quotes[1]])

	def test_a_full_award_gives_every_item_to_one_quotation(self):
		rfq, suppliers, quotes = self.standard_rfq()

		award = self.full_award(rfq, quotes[0])
		self.assertEqual(
			(award.supplier, award.rank, award.is_lowest, award.base_total), (suppliers[0], 1, 1, 900)
		)
		self.assertEqual([row.supplier_quotation for row in award.items], [quotes[0], quotes[0]])
		self.assertEqual([row.request_for_quotation_item for row in award.items], self.lines(rfq))
		award.submit()

		self.assertEqual(self.award_status(rfq), "Awarded")
		self.assertEqual(self.line_statuses(rfq), ["Awarded", "Awarded"])
		self.assertEqual(
			self.outcomes(rfq),
			{suppliers[0]: "Awarded", suppliers[1]: "Not Selected", suppliers[2]: "Not Selected"},
		)
		self.assertEqual(frappe.db.get_value("Supplier Quotation", quotes[0], "award_outcome"), "Awarded")
		self.assertEqual(
			frappe.db.get_value("Supplier Quotation", quotes[1], "award_outcome"), "Not Selected"
		)
		self.assertEqual(len(self.emails(rfq, "has been selected")), 1)
		self.assertEqual(len(self.emails(rfq, "was not selected")), 2)

	def test_a_full_award_to_a_higher_total_needs_a_justification(self):
		rfq, _, quotes = self.standard_rfq()

		self.assertRaisesRegex(frappe.ValidationError, "Justification", self.full_award, rfq, quotes[1])
		award = self.full_award(rfq, quotes[1], justification="Proven delivery record.")
		self.assertEqual((award.rank, award.is_lowest), (2, 0))

	def test_a_full_award_needs_a_quotation_for_every_open_item(self):
		rfq, _, quotes = self.quoted_rfq([100, 40], [80, 60])
		self.close_bids(rfq)
		self.open_bids(rfq)
		partial = frappe.get_doc("Supplier Quotation", quotes[1])
		partial.items = partial.items[:1]
		partial.flags.ignore_permissions = True
		partial.save()
		for quote in quotes:
			self.submit_quote(quote)

		self.assertRaisesRegex(frappe.ValidationError, "every open item", self.full_award, rfq, quotes[1])

	def test_a_full_award_refuses_a_quotation_from_another_request(self):
		rfq, _, _ = self.ready_rfq([100, 40])
		_, _, other_quotes = self.ready_rfq([90, 30])

		self.assertRaises(frappe.ValidationError, self.full_award, rfq, other_quotes[0])

	def test_a_partial_award_can_split_items_between_suppliers(self):
		rfq, suppliers, quotes = self.standard_rfq()
		first, second = self.lines(rfq)

		award = self.partial_award(
			rfq, [(first, {"supplier_quotation": quotes[1]}), (second, {"supplier_quotation": quotes[0]})]
		)
		self.assertEqual([row.is_lowest for row in award.items], [1, 1])
		self.assertEqual(award.base_total, 400 + 400)
		self.assertFalse(award.awarded_quotation)
		award.submit()

		self.assertEqual(self.award_status(rfq), "Awarded")
		self.assertEqual(
			self.outcomes(rfq),
			{suppliers[0]: "Awarded", suppliers[1]: "Awarded", suppliers[2]: "Not Selected"},
		)
		won = self.emails(rfq, "has been selected")
		self.assertEqual(len(won), 2)
		self.assertTrue(
			all(SECOND_ITEM in email["message"] or self.item in email["message"] for email in won)
		)
		self.assertEqual(len(self.emails(rfq, "was not selected")), 1)

	def test_leaving_an_item_open_partially_awards_the_request(self):
		rfq, suppliers, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)

		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()

		self.assertEqual(self.award_status(rfq), "Partially Awarded")
		self.assertEqual(self.line_statuses(rfq), ["Awarded", None])
		self.assertEqual(
			self.outcomes(rfq), {suppliers[0]: None, suppliers[1]: "Awarded", suppliers[2]: None}
		)
		self.assertFalse(self.emails(rfq, "was not selected"), "the others may still win the open item")

	def test_awarding_the_remaining_item_completes_the_request(self):
		rfq, suppliers, quotes = self.standard_rfq()
		first, second = self.lines(rfq)
		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()

		self.partial_award(rfq, [(second, {"supplier_quotation": quotes[0]})]).submit()

		self.assertEqual(self.award_status(rfq), "Awarded")
		self.assertEqual(self.outcomes(rfq)[suppliers[2]], "Not Selected")
		self.assertEqual(len(self.emails(rfq, "was not selected")), 1)

	def test_a_full_award_on_a_partially_awarded_request_covers_only_open_items(self):
		rfq, _, quotes = self.standard_rfq()
		first, second = self.lines(rfq)
		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()

		award = self.full_award(rfq, quotes[0])
		self.assertEqual([row.request_for_quotation_item for row in award.items], [second])
		self.assertEqual(award.base_total, 400)

	def test_a_partial_award_line_above_the_lowest_needs_its_own_justification(self):
		rfq, _, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)

		self.assertRaisesRegex(
			frappe.ValidationError,
			"Row #1.*Justification",
			self.partial_award,
			rfq,
			[(first, {"supplier_quotation": quotes[2]})],
		)
		award = self.partial_award(
			rfq, [(first, {"supplier_quotation": quotes[2], "justification": "Local supplier."})]
		)
		self.assertEqual((award.items[0].item_rank, award.items[0].is_lowest), (3, 0))

		lowest = self.partial_award(
			rfq, [(first, {"supplier_quotation": quotes[1], "justification": "Not needed."})]
		)
		self.assertFalse(lowest.items[0].justification, "the lowest price needs no justification")

	def test_a_partial_award_cannot_repeat_an_item(self):
		rfq, _, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)

		self.assertRaisesRegex(
			frappe.ValidationError,
			"more than once",
			self.partial_award,
			rfq,
			[(first, {"supplier_quotation": quotes[1]}), (first, {"supplier_quotation": quotes[0]})],
		)

	def test_a_partial_award_cannot_reaward_an_item(self):
		rfq, _, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)
		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()

		self.assertRaisesRegex(
			frappe.ValidationError,
			"not an open item",
			self.partial_award,
			rfq,
			[(first, {"supplier_quotation": quotes[0], "justification": "Second thoughts."})],
		)

	def test_a_partial_award_needs_a_price_for_the_item(self):
		rfq, _, quotes = self.quoted_rfq([100, 40], [80, 60])
		self.close_bids(rfq)
		self.open_bids(rfq)
		partial = frappe.get_doc("Supplier Quotation", quotes[1])
		partial.items = partial.items[:1]
		partial.flags.ignore_permissions = True
		partial.save()
		for quote in quotes:
			self.submit_quote(quote)
		_, second = self.lines(rfq)

		self.assertRaisesRegex(
			frappe.ValidationError,
			"no submitted price",
			self.partial_award,
			rfq,
			[(second, {"supplier_quotation": quotes[1], "justification": "Cheaper overall."})],
		)

	def test_a_partial_award_needs_at_least_one_item(self):
		rfq, _, _ = self.standard_rfq()
		self.assertRaisesRegex(frappe.ValidationError, "at least one item", self.partial_award, rfq, [])

	def test_an_expired_quotation_cannot_win(self):
		rfq, _, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)
		frappe.db.set_value("Supplier Quotation", quotes[0], "valid_till", add_days(nowdate(), -1))

		self.assertRaisesRegex(frappe.ValidationError, "expired", self.full_award, rfq, quotes[0])
		self.assertRaisesRegex(
			frappe.ValidationError,
			"expired",
			self.partial_award,
			rfq,
			[(first, {"supplier_quotation": quotes[0], "justification": "Cheaper overall."})],
		)
		self.assertTrue(self.full_award(rfq, quotes[1], justification="The cheapest one expired."))

	def test_a_disabled_supplier_cannot_win(self):
		rfq, suppliers, quotes = self.standard_rfq()
		frappe.db.set_value("Supplier", suppliers[0], "disabled", 1)

		self.assertRaisesRegex(frappe.ValidationError, "disabled", self.full_award, rfq, quotes[0])

	def test_a_supplier_on_hold_cannot_win_until_the_hold_is_released(self):
		rfq, suppliers, quotes = self.standard_rfq()
		frappe.db.set_value(
			"Supplier", suppliers[0], {"on_hold": 1, "hold_type": "All", "release_date": None}
		)
		self.assertRaisesRegex(frappe.ValidationError, "on hold", self.full_award, rfq, quotes[0])

		frappe.db.set_value("Supplier", suppliers[0], "release_date", add_days(nowdate(), -1))
		self.assertTrue(self.full_award(rfq, quotes[0]))

	def test_a_supplier_on_hold_for_payments_only_can_still_win(self):
		rfq, suppliers, quotes = self.standard_rfq()
		frappe.db.set_value("Supplier", suppliers[0], {"on_hold": 1, "hold_type": "Payments"})
		self.assertTrue(self.full_award(rfq, quotes[0]))

	def test_the_award_date_cannot_be_before_the_request(self):
		rfq, _, quotes = self.standard_rfq()
		self.assertRaisesRegex(
			frappe.ValidationError,
			"before the request date",
			self.full_award,
			rfq,
			quotes[0],
			award_date=add_days(nowdate(), -30),
		)

	def test_of_two_drafts_for_one_item_only_the_first_submitted_wins(self):
		rfq, _, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)
		one = self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})])
		two = self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})])

		one.submit()
		self.assertRaisesRegex(frappe.ValidationError, "not an open item", two.submit)

	def test_nothing_is_left_to_award_once_every_item_is_decided(self):
		rfq, _, quotes = self.standard_rfq()
		self.full_award(rfq, quotes[0]).submit()

		self.assertRaisesRegex(
			frappe.ValidationError, "already been awarded", self.full_award, rfq, quotes[1]
		)

	def test_closing_without_an_award_closes_every_item(self):
		rfq, _suppliers, quotes = self.standard_rfq()

		response = close_remaining_items(rfq.name, "Budget withdrawn.")

		self.assertEqual(response.data["award_status"], "Not Awarded")
		self.assertEqual(self.line_statuses(rfq), ["Not Awarded", "Not Awarded"])
		self.assertEqual(set(self.outcomes(rfq).values()), {"Not Selected"})
		self.assertEqual(frappe.db.get_value(RFQ, rfq.name, "award_remarks"), "Budget withdrawn.")
		self.assertEqual(len(self.emails(rfq, "was not selected")), 3)
		self.assertRaises(frappe.ValidationError, self.full_award, rfq, quotes[0])

	def test_closing_the_remaining_items_completes_a_partial_award(self):
		rfq, suppliers, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)
		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()

		close_remaining_items(rfq.name, "Second item no longer needed.")

		self.assertEqual(self.award_status(rfq), "Awarded")
		self.assertEqual(self.line_statuses(rfq), ["Awarded", "Not Awarded"])
		self.assertEqual(
			self.outcomes(rfq),
			{suppliers[0]: "Not Selected", suppliers[1]: "Awarded", suppliers[2]: "Not Selected"},
		)

	def test_only_an_open_request_can_be_closed(self):
		rfq, _, _ = self.quoted_rfq([100, 40])
		self.assertRaises(frappe.ValidationError, close_remaining_items, rfq.name, "Too early.")

	def test_cancelling_an_award_reopens_its_items(self):
		rfq, _, quotes = self.standard_rfq()
		award = self.full_award(rfq, quotes[0])
		award.submit()
		award.cancel()

		self.assertEqual(self.award_status(rfq), "Pending Selection")
		self.assertEqual(self.line_statuses(rfq), [None, None])
		self.assertEqual(set(self.outcomes(rfq).values()), {None})
		self.assertEqual(len(self.emails(rfq, "has been withdrawn")), 3)
		self.assertEqual(frappe.db.get_value(RFQ, rfq.name, "docstatus"), 1)
		self.assertEqual(
			set(frappe.get_all("Supplier Quotation", filters={"name": ("in", quotes)}, pluck="docstatus")),
			{1},
		)

	def test_cancelling_one_partial_award_reopens_only_its_items(self):
		rfq, _, quotes = self.standard_rfq()
		first, second = self.lines(rfq)
		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()
		later = self.partial_award(rfq, [(second, {"supplier_quotation": quotes[0]})])
		later.submit()

		later.cancel()

		self.assertEqual(self.award_status(rfq), "Partially Awarded")
		self.assertEqual(self.line_statuses(rfq), ["Awarded", None])

	def test_an_unawarded_quotation_cannot_be_ordered(self):
		rfq, _, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)
		self.assertRaisesRegex(frappe.ValidationError, "not been awarded", make_purchase_order, quotes[1])

		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()
		self.assertRaisesRegex(frappe.ValidationError, "not been awarded", make_purchase_order, quotes[0])

	def test_the_order_from_an_awarded_quotation_holds_only_awarded_items(self):
		rfq, _, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)
		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()

		order = make_purchase_order(quotes[1])
		self.assertEqual([row.item_code for row in order.items], [self.item])
		order.insert()
		self.assertEqual(order.docstatus, 0)

	def test_the_order_is_never_required_before_today(self):
		rfq, _, quotes = self.standard_rfq()
		frappe.db.set_value(RFQ, rfq.name, "schedule_date", None)
		for line in self.lines(rfq):
			frappe.db.set_value("Request for Quotation Item", line, "schedule_date", add_days(nowdate(), -10))
		self.full_award(rfq, quotes[0]).submit()

		order = make_purchase_order(quotes[0])
		order.insert()
		self.assertEqual({str(row.schedule_date) for row in order.items}, {nowdate()})

	def test_an_order_cannot_take_an_item_that_was_not_awarded(self):
		rfq, _, quotes = self.standard_rfq()
		first, second = self.lines(rfq)
		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()

		order = make_purchase_order(quotes[1])
		unawarded = next(
			row
			for row in frappe.get_doc("Supplier Quotation", quotes[1]).items
			if row.request_for_quotation_item == second
		)
		order.append(
			"items",
			{
				"item_code": unawarded.item_code,
				"qty": unawarded.qty,
				"rate": unawarded.rate,
				"schedule_date": getdate(add_days(nowdate(), 7)),
				"supplier_quotation": quotes[1],
				"supplier_quotation_item": unawarded.name,
			},
		)
		self.assertRaisesRegex(frappe.ValidationError, "not awarded", order.insert)

	def test_a_submitted_order_blocks_cancelling_the_award(self):
		rfq, _, quotes = self.standard_rfq()
		award = self.full_award(rfq, quotes[0])
		award.submit()
		order = make_purchase_order(quotes[0])
		order.insert()
		order.submit()

		award.reload()
		self.assertRaisesRegex(frappe.ValidationError, "before cancelling", award.cancel)

	def test_cancelling_the_award_removes_its_draft_orders(self):
		rfq, _, quotes = self.standard_rfq()
		award = self.full_award(rfq, quotes[0])
		award.submit()
		draft = make_purchase_order(quotes[0])
		draft.insert()

		award.reload()
		award.cancel()
		self.assertFalse(frappe.db.exists("Purchase Order", draft.name))

	def test_without_the_setting_no_order_is_drafted(self):
		rfq, _, quotes = self.standard_rfq()
		self.full_award(rfq, quotes[0]).submit()
		self.assertFalse(self.drafted_orders(quotes[0]))

	def test_the_setting_drafts_one_order_for_a_full_award(self):
		self.orders_on_award(True)
		rfq, suppliers, quotes = self.standard_rfq()
		self.full_award(rfq, quotes[0]).submit()

		orders = self.drafted_orders(quotes[0])
		self.assertEqual(len(orders), 1)
		order = frappe.get_doc("Purchase Order", orders[0])
		self.assertEqual((order.docstatus, order.supplier), (0, suppliers[0]))
		self.assertEqual(sorted(row.item_code for row in order.items), sorted([self.item, SECOND_ITEM]))

	def test_the_setting_drafts_an_order_per_winner_of_a_partial_award(self):
		self.orders_on_award(True)
		rfq, _suppliers, quotes = self.standard_rfq()
		first, second = self.lines(rfq)
		self.partial_award(
			rfq, [(first, {"supplier_quotation": quotes[1]}), (second, {"supplier_quotation": quotes[0]})]
		).submit()

		first_orders = self.drafted_orders(quotes[1])
		second_orders = self.drafted_orders(quotes[0])
		self.assertEqual((len(first_orders), len(second_orders)), (1, 1))
		self.assertEqual(
			[row.item_code for row in frappe.get_doc("Purchase Order", first_orders[0]).items], [self.item]
		)
		self.assertEqual(
			[row.item_code for row in frappe.get_doc("Purchase Order", second_orders[0]).items], [SECOND_ITEM]
		)
		self.assertFalse(self.drafted_orders(quotes[2]))

	def test_the_setting_drafts_only_this_awards_items(self):
		self.orders_on_award(True)
		rfq, _, quotes = self.standard_rfq()
		first, second = self.lines(rfq)
		self.partial_award(
			rfq, [(first, {"supplier_quotation": quotes[0], "justification": "Preferred."})]
		).submit()
		self.partial_award(rfq, [(second, {"supplier_quotation": quotes[0]})]).submit()

		items = sorted(
			tuple(row.item_code for row in frappe.get_doc("Purchase Order", order).items)
			for order in self.drafted_orders(quotes[0])
		)
		self.assertEqual(items, sorted([(self.item,), (SECOND_ITEM,)]))

	def test_a_purchase_order_cancels_on_its_own(self):
		from frappe.desk.form.linked_with import get_submitted_linked_docs

		rfq, _, quotes = self.standard_rfq()
		award = self.full_award(rfq, quotes[0])
		award.submit()
		order = make_purchase_order(quotes[0])
		order.insert()
		order.submit()

		linked = {row["doctype"] for row in get_submitted_linked_docs("Purchase Order", order.name)["docs"]}
		self.assertNotIn(AWARD, linked)
		self.assertNotIn(RFQ, linked)

		order.cancel()
		self.assertEqual(frappe.db.get_value(AWARD, award.name, "docstatus"), 1)
		self.assertEqual(self.award_status(rfq), "Awarded")

	def test_the_award_shows_in_the_request_and_quotation_connections(self):
		for doctype in (RFQ, "Supplier Quotation"):
			items = [
				item
				for group in frappe.get_meta(doctype).get_dashboard_data().transactions
				for item in group["items"]
			]
			self.assertEqual(items.count(AWARD), 1, doctype)

	def test_the_portal_shows_each_supplier_what_they_won(self):
		rfq, suppliers, quotes = self.standard_rfq()
		first, _ = self.lines(rfq)
		self.partial_award(rfq, [(first, {"supplier_quotation": quotes[1]})]).submit()
		winner = frappe.get_all("Portal User", filters={"parent": suppliers[1]}, pluck="user")[0]
		waiting = frappe.get_all("Portal User", filters={"parent": suppliers[2]}, pluck="user")[0]

		with self.set_user(winner):
			detail = get_rfq(rfq.name)
			self.assertEqual(get_rfqs(status="Awarded")["counts"].get("Awarded"), 1)
		self.assertEqual(detail["status"], "Awarded")
		self.assertEqual([item["awarded_to_you"] for item in detail["items"]], [True, False])

		with self.set_user(waiting):
			self.assertEqual(get_rfq(rfq.name)["status"], "Submitted")

		close_remaining_items(rfq.name, "Done.")
		with self.set_user(waiting):
			detail = get_rfq(rfq.name)
		self.assertEqual(detail["status"], "Not Selected")
		self.assertNotIn("rank", frappe.as_json(detail))

	def test_suppliers_and_buyers_without_award_rights_cannot_decide(self):
		rfq, suppliers, _ = self.standard_rfq()
		supplier_user = frappe.get_all("Portal User", filters={"parent": suppliers[0]}, pluck="user")[0]
		clerk = make_test_user(["Purchase User"], first_name="Clerk").name

		with self.set_user(supplier_user):
			self.assertRaises(frappe.PermissionError, get_award_overview, rfq.name)
		with self.set_user(clerk):
			self.assertRaises(frappe.PermissionError, close_remaining_items, rfq.name, "No.")

	def test_the_hourly_refresh_leaves_requests_still_bidding_alone(self):
		rfq, _, _ = self.quoted_rfq([100, 40])
		rfq.db_set("bid_closing", add_to_date(now_datetime(), hours=2))
		refresh_pending_selection()
		self.assertFalse(self.award_status(rfq))
