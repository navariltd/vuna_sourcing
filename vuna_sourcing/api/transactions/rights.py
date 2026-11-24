# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _

READ = "read"
CREATE = "create"
WRITE = "write"
DELETE = "delete"
PRINT = "print"

PORTAL_RIGHTS = (READ, CREATE, WRITE, DELETE, PRINT)
CHANGING_RIGHTS = frozenset({CREATE, WRITE, DELETE, "submit", "cancel", "amend"})

ACTION_LABEL = {
	READ: "view",
	CREATE: "create",
	WRITE: "change",
	DELETE: "delete",
	PRINT: "print",
}


def can(doctype: str, right: str, user: str | None = None) -> bool:
	return bool(frappe.has_permission(doctype, right, user=user or frappe.session.user))


def require(doctype: str, right: str, *alternatives: str) -> None:
	if any(can(doctype, option) for option in (right, *alternatives)):
		return

	frappe.throw(
		_(
			"Your account is not allowed to {0} {1} documents. Ask your contact on our team to switch it on."
		).format(_(ACTION_LABEL.get(right, right)), _(doctype)),
		frappe.PermissionError,
		title=_("Not Allowed"),
	)


def rights_of(doctypes: tuple[str, ...], user: str | None = None) -> dict[str, dict[str, bool]]:
	return {doctype: {right: can(doctype, right, user) for right in PORTAL_RIGHTS} for doctype in doctypes}
