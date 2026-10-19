# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from vuna_sourcing.api.transactions.award import (
	award_blockers,
	bids_by_line,
	creates_orders_on_award,
	make_award_orders,
	notify_award,
	notify_not_selected,
	notify_withdrawn,
	open_lines,
	orders_against,
	outcomes,
	quotation_problems,
	ranked_quotes,
	refresh_award_status,
)
from vuna_sourcing.api.transactions.bidding import FULL_AWARD
from vuna_sourcing.api.transactions.supplier import PURCHASE_ORDER, RFQ


class RequestforQuotationAward(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from vuna_sourcing.vuna_sourcing.doctype.request_for_quotation_award_item.request_for_quotation_award_item import (
			RequestforQuotationAwardItem,
		)

		amended_from: DF.Link | None
		award_basis: DF.Literal["Full Award", "Partial Award"]
		award_date: DF.Date
		base_total: DF.Currency
		bidding_method: DF.Data | None
		company: DF.Link | None
		is_lowest: DF.Check
		items: DF.Table[RequestforQuotationAwardItem]
		justification: DF.SmallText | None
		naming_series: DF.Literal["PUR-RFQA-.YYYY.-"]
		rank: DF.Int
		request_for_quotation: DF.Link
		supplier: DF.Link | None
		supplier_name: DF.Data | None
		awarded_quotation: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.validate_request()
		lines = open_lines(self.request_for_quotation)
		if not lines:
			frappe.throw(
				_("Every item on {0} has already been awarded or closed.").format(self.request_for_quotation),
				title=_("Nothing left to award"),
			)

		if self.award_basis == FULL_AWARD:
			self.set_full_award(lines)
		else:
			self.set_partial_award(lines)

		if problems := quotation_problems({row.supplier_quotation for row in self.items}, self.award_date):
			frappe.throw("<br>".join(problems), title=_("These quotations cannot win"))

		self.base_total = sum(flt(row.base_amount) for row in self.items)

	def validate_request(self):
		request = frappe.get_doc(RFQ, self.request_for_quotation)
		if blockers := award_blockers(request):
			frappe.throw("<br>".join(blockers), title=_("{0} is not ready to award").format(request.name))

		if getdate(self.award_date) < getdate(request.transaction_date):
			frappe.throw(
				_("Award Date cannot be before the request date {0}.").format(
					frappe.format(request.transaction_date, "Date")
				)
			)

	def set_full_award(self, lines):
		quote = next(
			(
				quote
				for quote in ranked_quotes(self.request_for_quotation, [line.name for line in lines])
				if quote.supplier_quotation == self.awarded_quotation
			),
			None,
		)
		if not quote:
			frappe.throw(
				_("{0} is not a submitted quotation for every open item on {1}.").format(
					frappe.bold(self.awarded_quotation), self.request_for_quotation
				),
				title=_("Choose another quotation"),
			)

		self.supplier = quote.supplier
		self.supplier_name = quote.supplier_name
		self.rank = quote.rank
		self.is_lowest = int(quote.is_lowest)
		if not self.is_lowest and not (self.justification or "").strip():
			frappe.throw(
				_("{0} is not the lowest total. Explain why it wins in Justification.").format(
					self.awarded_quotation
				),
				title=_("Justification needed"),
			)

		bids = bids_by_line(self.request_for_quotation)
		self.items = []
		for line in lines:
			bid = next(bid for bid in bids[line.name] if bid.supplier_quotation == self.awarded_quotation)
			self.append("items", award_row(line, bid))

	def set_partial_award(self, lines):
		self.awarded_quotation = None
		self.supplier = None
		self.supplier_name = None
		self.rank = 0
		self.is_lowest = 0
		self.justification = None

		if not self.items:
			frappe.throw(_("Add at least one item to award."), title=_("No items"))

		open_by_name = {line.name: line for line in lines}
		bids = bids_by_line(self.request_for_quotation)
		seen = set()

		for row in self.items:
			line = open_by_name.get(row.request_for_quotation_item)
			label = frappe.bold(row.item_name or row.item_code or row.request_for_quotation_item)
			if not line:
				frappe.throw(
					_("Row #{0}: {1} is not an open item on {2}.").format(
						row.idx, label, self.request_for_quotation
					),
					title=_("Item not open"),
				)
			if line.name in seen:
				frappe.throw(_("Row #{0}: {1} is awarded more than once.").format(row.idx, label))
			seen.add(line.name)

			bid = next(
				(bid for bid in bids.get(line.name, []) if bid.supplier_quotation == row.supplier_quotation),
				None,
			)
			if not bid:
				frappe.throw(
					_("Row #{0}: {1} has no submitted price for {2}.").format(
						row.idx, frappe.bold(row.supplier_quotation), label
					),
					title=_("No price for this item"),
				)

			justification = row.justification
			row.update(award_row(line, bid))
			row.justification = None if bid.is_lowest else justification
			if not bid.is_lowest and not (row.justification or "").strip():
				frappe.throw(
					_(
						"Row #{0}: {1} is not the lowest price for {2}. Explain why it wins in Justification."
					).format(row.idx, row.supplier_quotation, label),
					title=_("Justification needed"),
				)

	def on_submit(self):
		before = outcomes(self.request_for_quotation)
		refresh_award_status(self.request_for_quotation)
		notify_award(self)
		notify_not_selected(self.request_for_quotation, before)

		if creates_orders_on_award():
			orders = make_award_orders(self)
			frappe.msgprint(
				_("Draft Purchase Orders created for review: {0}").format(
					", ".join(frappe.get_desk_link(PURCHASE_ORDER, order) for order in orders)
				),
				title=_("Purchase Orders drafted"),
				indicator="green",
			)

	def awarded_lines(self) -> list[str]:
		return [row.supplier_quotation_item for row in self.items]

	def before_cancel(self):
		if orders := orders_against(self.awarded_lines(), docstatus=1):
			frappe.throw(
				_("Cancel {0} before cancelling this award.").format(
					", ".join(frappe.get_desk_link(PURCHASE_ORDER, order) for order in orders)
				),
				title=_("Purchase Order already submitted"),
			)

	def on_cancel(self):
		for order in orders_against(self.awarded_lines(), docstatus=0):
			frappe.delete_doc(PURCHASE_ORDER, order, ignore_permissions=True)

		before = outcomes(self.request_for_quotation)
		refresh_award_status(self.request_for_quotation)
		notify_withdrawn(self.request_for_quotation, before)


def award_row(line, bid) -> dict:
	return {
		"request_for_quotation_item": line.name,
		"item_code": line.item_code,
		"item_name": line.item_name,
		"qty": bid.qty,
		"uom": line.uom,
		"supplier_quotation": bid.supplier_quotation,
		"supplier_quotation_item": bid.supplier_quotation_item,
		"supplier": bid.supplier,
		"currency": bid.currency,
		"rate": bid.rate,
		"amount": bid.amount,
		"base_rate": bid.base_rate,
		"base_amount": bid.base_amount,
		"item_rank": bid.item_rank,
		"is_lowest": int(bid.is_lowest),
	}
