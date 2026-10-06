# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

BID_LOG = "RFQ Bid Log"
BID_PLACED = "open_bid_placed"


class RFQBidLog(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("A bid log entry cannot be changed."), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(_("A bid log entry cannot be deleted."), frappe.PermissionError)

	def after_insert(self):
		for user in bidder_users(self.request_for_quotation) - {self.placed_by}:
			frappe.publish_realtime(
				BID_PLACED, {"rfq": self.request_for_quotation}, user=user, after_commit=True
			)


def bidder_users(request: str) -> set[str]:
	suppliers = frappe.get_all(
		"Request for Quotation Supplier",
		filters={"parent": request, "parenttype": "Request for Quotation", "quote_status": "Received"},
		pluck="supplier",
	)
	return set(
		frappe.get_all(
			"Portal User",
			filters={"parenttype": "Supplier", "parent": ("in", suppliers or [""])},
			pluck="user",
		)
	)


def record_bid(quote, request: str):
	return frappe.get_doc(
		{
			"doctype": BID_LOG,
			"request_for_quotation": request,
			"supplier": quote.supplier,
			"supplier_quotation": quote.name,
			"revision": frappe.db.count(
				BID_LOG, {"request_for_quotation": request, "supplier": quote.supplier}
			)
			+ 1,
			"placed_at": now_datetime(),
			"placed_by": frappe.session.user,
			"company": quote.company,
			"currency": quote.currency,
			"conversion_rate": quote.conversion_rate,
			"valid_till": quote.valid_till,
			"total": quote.total,
			"base_total": quote.base_total,
			"items": [
				{
					"request_for_quotation_item": row.request_for_quotation_item,
					"item_code": row.item_code,
					"qty": row.qty,
					"uom": row.uom,
					"rate": row.rate,
					"base_rate": row.base_rate,
					"amount": row.amount,
					"lead_time_days": row.lead_time_days,
				}
				for row in quote.items
				if row.request_for_quotation == request
			],
		}
	).insert(ignore_permissions=True)
