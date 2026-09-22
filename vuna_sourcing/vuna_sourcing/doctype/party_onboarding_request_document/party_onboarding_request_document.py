# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PartyOnboardingRequestDocument(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		attachment: DF.Attach | None
		description: DF.SmallText | None
		document_number: DF.Data | None
		document_type: DF.Link
		expiry_date: DF.Date | None
		is_mandatory: DF.Check
		is_verified: DF.Check
		issue_date: DF.Date | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		remarks: DF.SmallText | None
		verified_by: DF.Link | None
		verified_on: DF.Datetime | None
	# end: auto-generated types

	pass
