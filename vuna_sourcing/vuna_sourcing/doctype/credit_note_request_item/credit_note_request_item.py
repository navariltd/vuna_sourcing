# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CreditNoteRequestItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		discount_percentage: DF.Percent
		item_code: DF.Link | None
		item_name: DF.Data | None
		new_rate: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		qty: DF.Float
		rate: DF.Currency
		sales_invoice_item: DF.Data | None
		uom: DF.Link | None
	# end: auto-generated types

	pass
