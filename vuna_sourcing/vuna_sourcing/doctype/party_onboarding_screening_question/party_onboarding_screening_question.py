# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PartyOnboardingScreeningQuestion(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		field_type: DF.Literal[
			"Short Text", "Long Text", "Whole Number", "Number", "Date", "Yes / No", "Multiple Choice"
		]
		is_mandatory: DF.Check
		options: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		question: DF.SmallText
	# end: auto-generated types

	pass
