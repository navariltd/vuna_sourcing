# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from vuna_sourcing.api.transactions.open_bid import get_bid_history, get_open_bids
from vuna_sourcing.api.transactions.supplier import (
	decline_quote,
	get_rfq,
	get_rfqs,
	save_quote,
	send_quote,
)
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures


class TestOpenBid(SourcingFixtures, IntegrationTestCase):
	"""On an open bid, suppliers see each other's bids anonymously and can bid again until bids close."""

	def make_open_rfq(self, suppliers):
		return self.make_rfq(suppliers, bidding_method="Open Bid")

	def bid(self, rfq, user, rate):
		with self.set_user(user):
			return send_quote(
				rfq.name, items=self.lines(get_rfq(rfq.name), rate=rate), valid_till=add_days(nowdate(), 30)
			)

	def board(self, rfq, user):
		with self.set_user(user):
			return get_open_bids(rfq.name).data

	def bid_logs(self, quote):
		return frappe.get_all(
			"RFQ Bid Log",
			filters={"supplier_quotation": quote},
			fields=["name", "revision", "total"],
			order_by="revision asc",
		)

	def staff(self):
		return make_test_user(["Purchase User"], first_name="Buyer").name

	def test_a_new_bid_updates_the_same_quotation_and_is_logged(self):
		supplier, user = self.make_supplier()
		rfq = self.make_open_rfq([supplier])

		first = self.bid(rfq, user, rate=100)
		self.assertTrue(first["open_bid"])
		self.assertTrue(first["can_quote"], "an open bid can be improved until bids close")

		second = self.bid(rfq, user, rate=90)

		name = first["quote"]["name"]
		self.assertEqual(second["quote"]["name"], name, "one quotation follows all of a supplier's bids")
		self.assertEqual(frappe.db.count("Supplier Quotation", {"supplier": supplier}), 1)
		self.assertEqual(second["items"][0]["rate"], 90)
		self.assertEqual(second["status"], "Bidding")
		self.assertEqual([(log.revision, log.total) for log in self.bid_logs(name)], [(1, 500), (2, 450)])

		latest = frappe.get_doc("RFQ Bid Log", self.bid_logs(name)[-1].name)
		self.assertEqual(latest.request_for_quotation, rfq.name)
		self.assertEqual([(row.qty, row.rate) for row in latest.items], [(5, 90)])

	def test_bid_logs_cannot_be_created_changed_or_deleted(self):
		supplier, user = self.make_supplier()
		rfq = self.make_open_rfq([supplier])
		log = self.bid_logs(self.bid(rfq, user, rate=100)["quote"]["name"])[0].name

		with self.set_user(self.staff()):
			self.assertFalse(frappe.has_permission("RFQ Bid Log", "create"))
			self.assertFalse(frappe.has_permission("RFQ Bid Log", "write", doc=log))
			self.assertTrue(frappe.has_permission("RFQ Bid Log", "read", doc=log))

		entry = frappe.get_doc("RFQ Bid Log", log)
		entry.total = 1
		self.assertRaises(frappe.PermissionError, entry.save, ignore_permissions=True)
		self.assertRaises(
			frappe.PermissionError, frappe.delete_doc, "RFQ Bid Log", log, ignore_permissions=True
		)

	def test_the_desk_cannot_edit_a_quotation_while_bidding(self):
		supplier, user = self.make_supplier()
		rfq = self.make_open_rfq([supplier])
		quote = frappe.get_doc("Supplier Quotation", self.bid(rfq, user, rate=100)["quote"]["name"])
		quote.flags.ignore_permissions = True

		with self.assertRaisesRegex(frappe.ValidationError, "still open"):
			quote.save()

		self.close_bids(rfq)
		quote.reload()
		quote.flags.ignore_permissions = True
		quote.save()

	def test_no_drafts_once_a_supplier_has_bid(self):
		supplier, user = self.make_supplier()
		rfq = self.make_open_rfq([supplier])
		self.bid(rfq, user, rate=100)

		with self.set_user(user):
			self.assertRaises(
				frappe.ValidationError, save_quote, rfq.name, items=self.lines(get_rfq(rfq.name), rate=1)
			)

	def test_the_quotation_shows_its_bid_history_newest_first(self):
		supplier, user = self.make_supplier()
		rfq = self.make_open_rfq([supplier])
		name = self.bid(rfq, user, rate=100)["quote"]["name"]
		self.bid(rfq, user, rate=90)
		self.bid(rfq, user, rate=95)

		with self.set_user(self.staff()):
			history = get_bid_history(name).data

		self.assertEqual(history["request_for_quotation"], rfq.name)
		self.assertEqual([bid["revision"] for bid in history["bids"]], [3, 2, 1])
		self.assertEqual([bid["change"] for bid in history["bids"]], [25, -50, None])
		self.assertEqual([line.rate for line in history["bids"][0]["items"]], [95])

	def test_a_sealed_bid_quotation_has_no_bid_history(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		name = self.bid(rfq, user, rate=100)["quote"]["name"]
		self.open_bids(rfq)

		self.assertEqual(get_bid_history(name).data["bids"], [])

	def test_the_board_ranks_bids_without_naming_suppliers(self):
		cheap, cheap_user = self.make_supplier()
		dear, dear_user = self.make_supplier()
		rfq = self.make_open_rfq([cheap, dear])
		self.bid(rfq, dear_user, rate=120)
		self.bid(rfq, cheap_user, rate=80)

		board = self.board(rfq, dear_user)

		self.assertEqual(board["bidders"], 2)
		self.assertEqual([row["alias"] for row in board["bids"]], ["Bidder B", "Bidder A"])
		self.assertEqual([row["rank"] for row in board["bids"]], [1, 2])
		self.assertEqual([row["is_you"] for row in board["bids"]], [False, True])
		self.assertEqual(board["lowest"], 400)

		published = frappe.as_json(board)
		for secret in (cheap, dear, *frappe.get_all("Supplier Quotation", {"supplier": cheap}, pluck="name")):
			self.assertNotIn(secret, published)

	def test_aliases_stay_the_same_when_a_supplier_bids_again(self):
		first, first_user = self.make_supplier()
		second, second_user = self.make_supplier()
		rfq = self.make_open_rfq([first, second])
		self.bid(rfq, first_user, rate=100)
		self.bid(rfq, second_user, rate=90)
		self.bid(rfq, first_user, rate=80)

		bids = self.board(rfq, second_user)["bids"]

		self.assertEqual(len(bids), 2, "only each supplier's latest bid is on the board")
		self.assertEqual((bids[0]["alias"], bids[0]["revisions"]), ("Bidder A", 2))
		self.assertEqual((bids[1]["alias"], bids[1]["revisions"]), ("Bidder B", 1))

	def test_live_bids_have_their_own_tab_until_bids_close(self):
		supplier, user = self.make_supplier()
		rfq = self.make_open_rfq([supplier])
		self.bid(rfq, user, rate=100)

		with self.set_user(user):
			self.assertEqual(get_rfqs(status="Bidding")["counts"], {"Bidding": 1})

		self.close_bids(rfq)
		with self.set_user(user):
			self.assertEqual(get_rfqs()["counts"], {"Submitted": 1})
			self.assertEqual(get_rfq(rfq.name)["status"], "Submitted")

	def test_the_board_lists_your_own_bids_newest_first(self):
		supplier, user = self.make_supplier()
		other, other_user = self.make_supplier()
		rfq = self.make_open_rfq([supplier, other])
		name = self.bid(rfq, user, rate=100)["quote"]["name"]
		self.bid(rfq, other_user, rate=95)
		self.bid(rfq, user, rate=90)

		yours = self.board(rfq, user)["your_bids"]

		self.assertEqual([bid["name"] for bid in yours], [log.name for log in reversed(self.bid_logs(name))])
		self.assertEqual([bid["live"] for bid in yours], [True, False])
		self.assertEqual([bid["total"] for bid in yours], [450, 500])

	def test_a_new_bid_signals_the_other_bidders(self):
		first, first_user = self.make_supplier()
		second, second_user = self.make_supplier()
		waiting, _waiting_user = self.make_supplier()
		rfq = self.make_open_rfq([first, second, waiting])
		self.bid(rfq, second_user, rate=100)

		with patch("frappe.publish_realtime") as publish:
			self.bid(rfq, first_user, rate=90)

		signals = [call for call in publish.call_args_list if call.args[:1] == ("open_bid_placed",)]
		self.assertEqual(
			{call.kwargs["user"] for call in signals},
			{second_user},
			"the bidder and suppliers yet to bid are not signalled",
		)
		for call in signals:
			self.assertEqual(call.args[1], {"rfq": rfq.name})
			self.assertTrue(call.kwargs["after_commit"])

	def test_the_board_opens_only_after_your_own_bid(self):
		bidder, bidder_user = self.make_supplier()
		waiting, waiting_user = self.make_supplier()
		_outsider, outsider_user = self.make_supplier()
		rfq = self.make_open_rfq([bidder, waiting])
		self.bid(rfq, bidder_user, rate=100)

		for user in (waiting_user, outsider_user):
			with self.set_user(user):
				self.assertRaises(frappe.PermissionError, get_open_bids, rfq.name)

	def test_no_new_bid_after_bids_close(self):
		supplier, user = self.make_supplier()
		rfq = self.make_open_rfq([supplier])
		self.bid(rfq, user, rate=100)
		self.close_bids(rfq)

		with self.set_user(user):
			self.assertFalse(get_rfq(rfq.name)["can_quote"])
		self.assertRaises(frappe.ValidationError, self.bid, rfq, user, 90)
		self.assertTrue(self.board(rfq, user)["closed"])

	def test_a_supplier_who_has_bid_cannot_decline(self):
		supplier, user = self.make_supplier()
		rfq = self.make_open_rfq([supplier])
		self.bid(rfq, user, rate=100)

		with self.set_user(user):
			self.assertRaises(frappe.ValidationError, decline_quote, rfq.name, reason="Changed my mind")

	def test_bids_are_submitted_only_after_bidding_closes(self):
		supplier, user = self.make_supplier()
		rfq = self.make_open_rfq([supplier])
		self.bid(rfq, user, rate=100)
		name = self.bid(rfq, user, rate=90)["quote"]["name"]

		quote = frappe.get_doc("Supplier Quotation", name)
		quote.flags.ignore_permissions = True
		with self.assertRaisesRegex(frappe.ValidationError, "still open"):
			quote.submit()

		self.close_bids(rfq)
		quote.reload()
		quote.flags.ignore_permissions = True
		quote.submit()
		self.assertEqual(quote.docstatus, 1)

	def test_a_sealed_bid_still_takes_one_quotation(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		sent = self.bid(rfq, user, rate=100)

		self.assertFalse(sent["open_bid"])
		self.assertFalse(sent["can_quote"])
		self.assertRaises(frappe.ValidationError, self.bid, rfq, user, 90)
		with self.set_user(user):
			self.assertRaises(frappe.PermissionError, get_open_bids, rfq.name)
