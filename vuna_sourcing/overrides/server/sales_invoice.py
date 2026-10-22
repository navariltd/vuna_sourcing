# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from vuna_sourcing.vuna_sourcing.doctype.credit_note_request.credit_note_request import (
	APPROVED,
	DOCTYPE,
	ISSUED,
	REQUEST_FIELD,
)


def credit_note_request_of(doc):
	name = doc.get(REQUEST_FIELD)
	return frappe.get_doc(DOCTYPE, name) if name else None


def validate_credit_note_request(doc, method=None):
	request = credit_note_request_of(doc)
	if not request:
		return

	if not doc.is_return or doc.return_against != request.sales_invoice:
		frappe.throw(
			_(
				"Credit note request {0} is for invoice {1}, so this must be a credit note against {1}."
			).format(request.name, request.sales_invoice),
			title=_("Wrong Invoice"),
		)

	if request.docstatus != 1 or request.request_status != APPROVED:
		frappe.throw(
			_("Credit note request {0} is {1}, so this credit note cannot be submitted.").format(
				request.name, _(request.request_status or "Draft").lower()
			),
			title=_("Request Not Approved"),
		)


def mark_credit_note_issued(doc, method=None):
	request = credit_note_request_of(doc)
	if not request:
		return

	request.db_set({"request_status": ISSUED, "credit_note": doc.name})
	request.add_comment("Comment", _("<b>Credit note {0} issued</b>").format(doc.name))
	request.notify_customer(
		_("Credit note {0} issued").format(doc.name),
		_("We have issued credit note {0} against invoice {1}, as you asked in request {2}.").format(
			doc.name, request.sales_invoice, request.name
		),
	)


def reopen_credit_note_request(doc, method=None):
	request = credit_note_request_of(doc)
	if not request or request.credit_note != doc.name:
		return

	request.db_set({"request_status": APPROVED, "credit_note": None})
	request.add_comment("Comment", _("<b>Credit note {0} cancelled</b>").format(doc.name))
