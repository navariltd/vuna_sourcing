# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RFQOpeningCommittee(Document):
	def validate(self):
		self.validate_unique_members()

	def validate_unique_members(self):
		users = [row.user for row in self.members]
		repeated = {user for user in users if users.count(user) > 1}
		if repeated:
			frappe.throw(_("Each member can only be listed once: {0}").format(", ".join(sorted(repeated))))

	def member_users(self) -> list[str]:
		return [row.user for row in self.members]
