# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, nowdate

from vuna_sourcing.tests import make_test_user


class SourcingFixtures:
	item = "_Test Portal RFQ Item"

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
		frappe.db.commit()

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

	def make_rfq(self, suppliers, required_by=None, qty=5):
		doc = frappe.get_doc(
			{
				"doctype": "Request for Quotation",
				"company": self.company,
				"transaction_date": nowdate(),
				"schedule_date": required_by or add_days(nowdate(), 7),
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
		return doc

	def lines(self, detail, rate=100, lead_time_days=3):
		return [
			{"rfq_item": item["name"], "rate": rate, "lead_time_days": lead_time_days}
			for item in detail["items"]
		]
