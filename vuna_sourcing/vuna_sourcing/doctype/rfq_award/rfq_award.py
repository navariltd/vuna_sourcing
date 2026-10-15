# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.award import (
	AWARD,
	award_blockers,
	creates_orders_on_award,
	decided_suppliers,
	live_orders_of,
	make_award_purchase_order,
	notify_outcomes,
	notify_withdrawn,
	orders_of,
	ranked_quotes,
	refresh_award_status,
)
from vuna_sourcing.api.transactions.bidding import NOT_AWARDED
from vuna_sourcing.api.transactions.supplier import PURCHASE_ORDER, RFQ, SUPPLIER_QUOTATION


class RFQAward(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		award_date: DF.Date
		base_total: DF.Currency
		bidding_method: DF.Data | None
		company: DF.Link | None
		currency: DF.Link | None
		is_lowest: DF.Check
		justification: DF.SmallText | None
		naming_series: DF.Literal["RFQ-AWD-.YYYY.-"]
		rank: DF.Int
		request_for_quotation: DF.Link
		supplier: DF.Link | None
		supplier_name: DF.Data | None
		supplier_quotation: DF.Link
		total: DF.Currency
	# end: auto-generated types

	def onload(self):
		self.set_onload("purchase_orders", live_orders_of(self.name))

	def validate(self):
		self.validate_request()
		self.set_quotation_details()
		self.validate_justification()

	def validate_request(self):
		request = frappe.get_doc(RFQ, self.request_for_quotation)

		if blockers := award_blockers(request):
			frappe.throw("<br>".join(blockers), title=_("{0} is not ready to award").format(request.name))

		if request.award_status == NOT_AWARDED:
			frappe.throw(_("{0} was closed without an award.").format(request.name))

		awarded = frappe.db.get_value(
			AWARD,
			{"request_for_quotation": request.name, "docstatus": 1, "name": ("!=", self.name)},
			"name",
		)
		if awarded:
			frappe.throw(
				_("{0} is already awarded by {1}.").format(request.name, frappe.bold(awarded)),
				title=_("Already awarded"),
			)

	def set_quotation_details(self):
		quote = next(
			(
				quote
				for quote in ranked_quotes(self.request_for_quotation)
				if quote.supplier_quotation == self.supplier_quotation
			),
			None,
		)
		if not quote:
			frappe.throw(
				_("{0} is not a submitted quotation for {1}.").format(
					frappe.bold(self.supplier_quotation), self.request_for_quotation
				)
			)

		self.supplier = quote.supplier
		self.supplier_name = quote.supplier_name
		self.currency = quote.currency
		self.total = quote.total
		self.base_total = quote.base_total
		self.rank = quote.rank
		self.is_lowest = int(quote.is_lowest)

	def validate_justification(self):
		if not self.is_lowest and not (self.justification or "").strip():
			frappe.throw(
				_("{0} is not the lowest quotation. Explain why it wins in Justification.").format(
					self.supplier_quotation
				),
				title=_("Justification needed"),
			)

	def on_submit(self):
		refresh_award_status(self.request_for_quotation)
		notify_outcomes(self.request_for_quotation)
		if creates_orders_on_award():
			make_award_purchase_order(self)

	def before_cancel(self):
		self.ignore_linked_doctypes = (RFQ, SUPPLIER_QUOTATION)
		if submitted := orders_of(self.name, docstatus=1):
			frappe.throw(
				_("Cancel {0} before cancelling this award.").format(
					", ".join(frappe.get_desk_link(PURCHASE_ORDER, order) for order in submitted)
				),
				title=_("Purchase Order already submitted"),
			)

	def on_cancel(self):
		notified = decided_suppliers(self.request_for_quotation)
		for order in orders_of(self.name, docstatus=0):
			frappe.delete_doc(PURCHASE_ORDER, order)
		refresh_award_status(self.request_for_quotation)
		notify_withdrawn(self.request_for_quotation, notified)

	@frappe.whitelist()
	def create_purchase_order(self) -> ApiResponse[dict]:
		if self.docstatus != 1:
			frappe.throw(_("Submit the award before creating its Purchase Order."))

		if existing := live_orders_of(self.name):
			frappe.throw(_("{0} already has Purchase Order {1}.").format(self.name, frappe.bold(existing[0])))

		frappe.has_permission(PURCHASE_ORDER, "create", throw=True)
		order = make_award_purchase_order(self)
		return ApiResponse.success(_("Purchase Order {0} created.").format(order), {"purchase_order": order})
