# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, add_to_date, get_datetime, getdate, now_datetime, nowdate

from vuna_sourcing.tests import make_test_user


class SourcingFixtures:
	item = "_Test Portal RFQ Item"
	committee = "_Test RFQ Opening Committee"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		if not frappe.db.exists("Item", cls.item):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": cls.item,
					"item_name": cls.item,
					"description": cls.item,
					"item_group": frappe.get_all(
						"Item Group", filters={"is_group": 0}, limit=1, pluck="name"
					)[0],
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)

		cls.company = frappe.get_all("Company", limit=1, pluck="name")[0]
		cls.warehouse = frappe.get_all(
			"Warehouse", filters={"is_group": 0, "company": cls.company}, limit=1, pluck="name"
		)[0]
		if not frappe.db.exists("RFQ Opening Committee", cls.committee):
			cls.make_committee(
				[make_test_user(["Purchase User"], first_name="Opener").name], name=cls.committee
			)
		frappe.db.commit()

	@staticmethod
	def make_committee(members, name=None):
		return (
			frappe.get_doc(
				{
					"doctype": "RFQ Opening Committee",
					"committee_name": name or "_Test Committee " + frappe.generate_hash(length=6),
					"members": [{"user": member} for member in members],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def make_supplier(self):
		user = make_test_user(["Supplier"], first_name="Supplier").name
		group = frappe.get_all("Supplier Group", filters={"is_group": 0}, limit=1, pluck="name")[0]
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": "_Test RFQ Supplier " + frappe.generate_hash(length=6),
				"supplier_group": group,
				"portal_users": [{"user": user}],
			}
		).insert(ignore_permissions=True)
		return supplier.name, user

	def make_customer(self):
		user = make_test_user(["Customer"], first_name="Customer").name
		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": "_Test Portal Customer " + frappe.generate_hash(length=6),
				"customer_group": frappe.get_all(
					"Customer Group", filters={"is_group": 0}, limit=1, pluck="name"
				)[0],
				"territory": frappe.get_all("Territory", filters={"is_group": 0}, limit=1, pluck="name")[0],
				"portal_users": [{"user": user}],
			}
		).insert(ignore_permissions=True)
		return customer.name, user

	def make_rfq(
		self,
		suppliers,
		required_by=None,
		qty=5,
		committee=None,
		minimum_expected_quotes=0,
		bidding_method="Sealed Bid",
	):
		doc = frappe.get_doc(
			{
				"doctype": "Request for Quotation",
				"company": self.company,
				"transaction_date": nowdate(),
				"schedule_date": required_by or add_days(nowdate(), 7),
				"bidding_method": bidding_method,
				"bid_closing": add_to_date(now_datetime(), days=7),
				"opening_committee": committee or self.committee,
				"minimum_expected_quotes": minimum_expected_quotes,
				"message_for_supplier": "Please quote your best price.",
				"suppliers": [{"supplier": supplier, "send_email": 0} for supplier in suppliers],
				"items": [
					{
						"item_code": self.item,
						"qty": qty,
						"uom": "Nos",
						"conversion_factor": 1,
						"warehouse": self.warehouse,
						"schedule_date": required_by or add_days(nowdate(), 7),
					}
				],
			}
		).insert(ignore_permissions=True)
		doc.submit()

		if required_by and getdate(required_by) < getdate(nowdate()):
			self.close_bids(doc, get_datetime(required_by))

		return doc

	def close_bids(self, rfq, at=None):
		rfq.db_set("bid_closing", at or add_to_date(now_datetime(), minutes=-1))

	def open_bids(self, rfq):
		rfq.db_set("quotes_opened", 1)

	def lines(self, detail, rate=100, lead_time_days=3):
		return [
			{"rfq_item": item["name"], "rate": rate, "lead_time_days": lead_time_days}
			for item in detail["items"]
		]
