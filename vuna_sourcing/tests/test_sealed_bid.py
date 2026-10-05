# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from zoneinfo import ZoneInfo

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, get_datetime, get_system_timezone, now_datetime, nowdate

from vuna_sourcing.api.transactions.sealed_bid import get_opening_status, open_quotes
from vuna_sourcing.api.transactions.supplier import decline_quote, get_rfq, save_quote, send_quote
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures

OPENING_EXCEPTIONS = (
	"allow_opening_before_bids_close",
	"allow_opening_below_minimum",
	"allow_any_member_to_open",
)


class TestSealedBid(SourcingFixtures, IntegrationTestCase):
	"""Quotations on a sealed bid stay hidden until the committee opens them together after bids close."""

	def setUp(self):
		super().setUp()
		for setting in OPENING_EXCEPTIONS:
			current = frappe.db.get_single_value("Sourcing Settings", setting)
			self.addCleanup(frappe.db.set_single_value, "Sourcing Settings", setting, current)
			frappe.db.set_single_value("Sourcing Settings", setting, 0)

	def committee_of(self, count=2):
		members = [make_test_user(["Purchase User"], first_name="Member").name for _ in range(count)]
		return self.make_committee(members), members

	def send(self, rfq, user):
		with self.set_user(user):
			return send_quote(
				rfq.name, items=self.lines(get_rfq(rfq.name)), valid_till=add_days(nowdate(), 30)
			)["quote"]["name"]

	def draft_rfq(self, **fields):
		return frappe.get_doc(
			{
				"doctype": "Request for Quotation",
				"company": self.company,
				"transaction_date": nowdate(),
				"schedule_date": add_days(nowdate(), 7),
				"bidding_method": "Sealed Bid",
				"bid_closing": add_to_date(now_datetime(), days=7),
				"opening_committee": self.committee,
				"suppliers": [{"supplier": self.make_supplier()[0], "send_email": 0}],
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"uom": "Nos",
						"conversion_factor": 1,
						"warehouse": self.warehouse,
						"schedule_date": add_days(nowdate(), 7),
					}
				],
				**fields,
			}
		)

	def test_a_sealed_bid_needs_a_committee(self):
		rfq = self.draft_rfq(opening_committee=None)
		self.assertRaises(frappe.ValidationError, rfq.insert, ignore_permissions=True)

	def test_bids_must_close_in_the_future_to_submit(self):
		rfq = self.draft_rfq(bid_closing=add_to_date(now_datetime(), hours=-1)).insert(
			ignore_permissions=True
		)
		self.assertRaises(frappe.ValidationError, rfq.submit)

	def test_submitting_assigns_the_committee(self):
		committee, members = self.committee_of()
		rfq = self.make_rfq([self.make_supplier()[0]], committee=committee)

		assigned = frappe.get_all(
			"ToDo",
			filters={"reference_type": rfq.doctype, "reference_name": rfq.name, "status": "Open"},
			pluck="allocated_to",
		)
		self.assertCountEqual(assigned, members)

	def test_suppliers_cannot_send_once_bids_close(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		self.close_bids(rfq)

		with self.set_user(user):
			self.assertTrue(get_rfq(rfq.name)["closed"])
			self.assertRaises(frappe.ValidationError, save_quote, rfq.name, items=[])

	def test_a_sent_quotation_stays_sealed_until_opened(self):
		committee, members = self.committee_of(count=1)
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier], committee=committee)
		name = self.send(rfq, user)

		with self.set_user(user):
			self.assertTrue(get_rfq(rfq.name)["sealed"])

		for viewer in members:
			with self.set_user(viewer):
				self.assertNotIn(name, frappe.get_list("Supplier Quotation", pluck="name"))
				self.assertFalse(frappe.has_permission("Supplier Quotation", doc=name))

		quote = frappe.get_doc("Supplier Quotation", name)
		quote.flags.ignore_permissions = True
		self.assertRaisesRegex(frappe.ValidationError, "sealed bid", quote.submit)

		self.close_bids(rfq)
		with self.set_user(members[0]):
			open_quotes(rfq.name)

		with self.set_user(members[0]):
			self.assertIn(name, frappe.get_list("Supplier Quotation", pluck="name"))

		quote.reload()
		quote.submit()
		self.assertEqual(quote.docstatus, 1)

	def test_quotations_cannot_be_opened_before_bids_close(self):
		committee, members = self.committee_of(count=1)
		rfq = self.make_rfq([self.make_supplier()[0]], committee=committee)

		with self.set_user(members[0]):
			self.assertFalse(get_opening_status(rfq.name).data["can_confirm"])
			self.assertRaises(frappe.ValidationError, open_quotes, rfq.name)

	def test_only_committee_members_can_open(self):
		rfq = self.make_rfq([self.make_supplier()[0]])
		self.close_bids(rfq)
		outsider = make_test_user(["Purchase User"], first_name="Outsider").name

		with self.set_user(outsider):
			self.assertRaises(frappe.PermissionError, open_quotes, rfq.name)

	def test_opening_waits_for_the_minimum_number_of_quotations(self):
		committee, members = self.committee_of(count=1)
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier], committee=committee, minimum_expected_quotes=2)
		self.send(rfq, user)
		self.close_bids(rfq)

		with self.set_user(members[0]):
			self.assertRaisesRegex(frappe.ValidationError, "1 received, 2 required", open_quotes, rfq.name)

		rfq.reload()
		self.assertFalse(rfq.quotes_opened)
		self.assertEqual(rfq.opening_confirmations, [])

	def test_every_member_must_confirm_before_the_quotations_open(self):
		committee, members = self.committee_of(count=3)
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier], committee=committee)
		name = self.send(rfq, user)
		self.close_bids(rfq)

		for confirmed, member in enumerate(members[:2], start=1):
			with self.set_user(member):
				status = open_quotes(rfq.name).data
				self.assertFalse(status["opened"])
				self.assertEqual(status["confirmations"], confirmed)
				self.assertNotIn(name, frappe.get_list("Supplier Quotation", pluck="name"))

		with self.set_user(members[0]):
			self.assertRaises(frappe.ValidationError, open_quotes, rfq.name)

		with self.set_user(members[2]):
			status = open_quotes(rfq.name).data
			self.assertTrue(status["opened"])
			self.assertEqual(status["received"], 1)
			self.assertIn(name, frappe.get_list("Supplier Quotation", pluck="name"))

		rfq.reload()
		self.assertTrue(rfq.quotes_opened)
		self.assertEqual([row.member for row in rfq.opening_confirmations], members)
		self.assertFalse(
			frappe.get_all(
				"ToDo",
				filters={"reference_type": rfq.doctype, "reference_name": rfq.name, "status": "Open"},
			),
			"the committee's opening tasks close once the quotations are open",
		)

	def test_drafts_stay_hidden_after_opening(self):
		committee, members = self.committee_of(count=1)
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier], committee=committee)

		with self.set_user(user):
			draft = save_quote(rfq.name, items=self.lines(get_rfq(rfq.name))).data["quote"]["name"]

		self.close_bids(rfq)
		with self.set_user(members[0]):
			self.assertEqual(open_quotes(rfq.name).data["received"], 0, "a draft is not a received quotation")
			self.assertNotIn(draft, frappe.get_list("Supplier Quotation", pluck="name"))

	def allow(self, setting):
		frappe.db.set_single_value("Sourcing Settings", setting, 1)

	def test_every_opening_condition_is_required_by_default(self):
		rfq = self.make_rfq([self.make_supplier()[0]])

		conditions = get_opening_status(rfq.name).data["conditions"]

		self.assertEqual(
			{condition["key"]: condition["required"] for condition in conditions},
			{"bids_closed": True, "minimum_quotations": True, "committee_confirmed": True},
		)

	def test_quotations_can_open_before_bids_close_when_allowed(self):
		self.allow("allow_opening_before_bids_close")
		committee, members = self.committee_of(count=1)
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier], committee=committee)
		self.send(rfq, user)

		with self.set_user(members[0]):
			status = get_opening_status(rfq.name).data
			self.assertFalse(next(c for c in status["conditions"] if c["key"] == "bids_closed")["required"])
			self.assertTrue(status["can_confirm"])
			self.assertTrue(open_quotes(rfq.name).data["opened"])

		with self.set_user(user):
			self.assertTrue(get_rfq(rfq.name)["closed"], "opening early stops further quotations")
			self.assertRaises(frappe.ValidationError, save_quote, rfq.name, items=[])

	def test_quotations_can_open_below_the_minimum_when_allowed(self):
		self.allow("allow_opening_below_minimum")
		committee, members = self.committee_of(count=1)
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier], committee=committee, minimum_expected_quotes=3)
		self.send(rfq, user)
		self.close_bids(rfq)

		with self.set_user(members[0]):
			status = open_quotes(rfq.name).data

		self.assertTrue(status["opened"])
		self.assertEqual(status["received"], 1)

	def test_any_one_member_can_open_when_allowed(self):
		self.allow("allow_any_member_to_open")
		committee, members = self.committee_of(count=3)
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier], committee=committee)
		name = self.send(rfq, user)
		self.close_bids(rfq)

		with self.set_user(members[1]):
			self.assertTrue(open_quotes(rfq.name).data["opened"])
			self.assertIn(name, frappe.get_list("Supplier Quotation", pluck="name"))

		self.assertFalse(
			frappe.get_all(
				"ToDo",
				filters={"reference_type": rfq.doctype, "reference_name": rfq.name, "status": "Open"},
			),
			"the other members' opening tasks close too",
		)

	def test_declines_are_shown_but_do_not_count_toward_the_minimum(self):
		committee, members = self.committee_of(count=1)
		quoting, quoting_user = self.make_supplier()
		declining, declining_user = self.make_supplier()
		rfq = self.make_rfq([quoting, declining], committee=committee, minimum_expected_quotes=2)
		self.send(rfq, quoting_user)
		with self.set_user(declining_user):
			decline_quote(rfq.name, reason="Out of stock")
		self.close_bids(rfq)

		minimum = next(
			condition
			for condition in get_opening_status(rfq.name).data["conditions"]
			if condition["key"] == "minimum_quotations"
		)
		self.assertFalse(minimum["met"])
		self.assertEqual(minimum["detail"], "1 received, 1 declined, 2 required")

		with self.set_user(members[0]):
			self.assertRaises(frappe.ValidationError, open_quotes, rfq.name)

	def test_the_portal_gets_the_closing_time_with_its_time_zone(self):
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])

		with self.set_user(user):
			closes_at = get_rfq(rfq.name)["closes_at"]

		self.assertEqual(get_datetime(closes_at).replace(tzinfo=None), get_datetime(rfq.bid_closing))
		self.assertEqual(
			get_datetime(closes_at).utcoffset(),
			ZoneInfo(get_system_timezone()).utcoffset(get_datetime(rfq.bid_closing)),
			"the browser can place the time correctly whatever its own zone",
		)
