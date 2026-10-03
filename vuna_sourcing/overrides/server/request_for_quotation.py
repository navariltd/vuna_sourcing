# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from vuna_sourcing.api.transactions.bidding import SEALED_BID
from vuna_sourcing.api.transactions.sealed_bid import COMMITTEE, assign_committee


def validate(doc, method: str | None = None) -> None:
	if doc.bidding_method != SEALED_BID:
		return

	if not doc.opening_committee:
		frappe.throw(_("A sealed bid needs an RFQ Opening Committee to open the quotations."))

	if frappe.db.get_value(COMMITTEE, doc.opening_committee, "disabled"):
		frappe.throw(_("{0} is disabled.").format(frappe.bold(doc.opening_committee)))


def before_submit(doc, method: str | None = None) -> None:
	if not doc.bid_closing or get_datetime(doc.bid_closing) <= now_datetime():
		frappe.throw(_("Set when bids close to a time in the future before submitting."))


def on_submit(doc, method: str | None = None) -> None:
	if doc.bidding_method == SEALED_BID:
		assign_committee(doc)
