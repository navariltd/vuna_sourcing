# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from vuna_sourcing.api.transactions.open_bid import running_open_bid_of
from vuna_sourcing.api.transactions.sealed_bid import sealed_request_of
from vuna_sourcing.api.transactions.supplier import QUOTE_PENDING, SUBMISSION_STATUS_FIELD


def validate(doc, method: str | None = None) -> None:
	if doc.is_new() or doc.flags.placing_bid:
		return

	if running := running_open_bid_of(doc):
		frappe.throw(
			_(
				"Bidding on {0} is still open. This quotation follows the supplier's bids until bids close."
			).format(frappe.bold(running)),
			title=_("Bidding still open"),
		)


def validate_submittable(doc, method: str | None = None) -> None:
	if doc.get(SUBMISSION_STATUS_FIELD) == QUOTE_PENDING:
		frappe.throw(
			_("{0} has not finalised this quotation yet. It can be submitted once they send it.").format(
				frappe.bold(doc.supplier_name or doc.supplier)
			),
			title=_("Quotation not sent"),
		)

	if running := running_open_bid_of(doc):
		frappe.throw(
			_("Bidding on {0} is still open. Its quotations can be submitted once bids close.").format(
				frappe.bold(running)
			),
			title=_("Bidding still open"),
		)

	if sealed := sealed_request_of(doc):
		frappe.throw(
			_("{0} is a sealed bid. Its quotations can be submitted once the committee opens them.").format(
				frappe.bold(sealed)
			),
			title=_("Quotation still sealed"),
		)
