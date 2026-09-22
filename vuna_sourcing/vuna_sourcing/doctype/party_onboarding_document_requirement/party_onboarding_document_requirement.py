# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PartyOnboardingDocumentRequirement(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		document_type: DF.Link
		has_expiry: DF.Check
		is_mandatory: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types

	pass
