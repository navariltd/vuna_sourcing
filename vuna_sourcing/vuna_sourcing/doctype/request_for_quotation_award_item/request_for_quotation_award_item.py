# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class RequestforQuotationAwardItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		base_amount: DF.Currency
		base_rate: DF.Currency
		currency: DF.Link | None
		is_lowest: DF.Check
		item_code: DF.Link | None
		item_name: DF.Data | None
		item_rank: DF.Int
		justification: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		qty: DF.Float
		rate: DF.Currency
		request_for_quotation_item: DF.Data | None
		supplier: DF.Link | None
		supplier_quotation: DF.Link
		supplier_quotation_item: DF.Data | None
		uom: DF.Link | None
	# end: auto-generated types

	pass
