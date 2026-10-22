# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from frappe import _

from vuna_sourcing.api.transactions.bidding import AWARD
from vuna_sourcing.vuna_sourcing.doctype.credit_note_request.credit_note_request import (
	DOCTYPE as CREDIT_NOTE_REQUEST,
)


def with_award(data: dict) -> dict:
	items = data["transactions"][0]["items"]
	if AWARD not in items:
		items.append(AWARD)
	return data


def request_for_quotation(data: dict) -> dict:
	return with_award(data)


def supplier_quotation(data: dict) -> dict:
	return with_award(data)


def sales_invoice(data: dict) -> dict:
	returns = next((group for group in data["transactions"] if "Sales Invoice" in group["items"]), None)
	if returns is None:
		data["transactions"].append({"label": _("Returns"), "items": [CREDIT_NOTE_REQUEST]})
	elif CREDIT_NOTE_REQUEST not in returns["items"]:
		returns["items"].append(CREDIT_NOTE_REQUEST)
	return data
