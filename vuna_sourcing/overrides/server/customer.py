# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cstr

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.branches import (
	ACCOUNT_ADMIN_FIELD,
	BRANCHES_FIELD,
	branch_title,
	join_branches,
	linked_addresses,
	parse_branches,
)
from vuna_sourcing.utils import CUSTOMER

PORTAL_USERS_FIELD = "portal_users"
SEARCH_LIMIT = 20
MAX_SELECTED = 200


def saved_branches(doc) -> dict[str, set[str]]:
	before = doc.get_doc_before_save()
	if not before:
		return {}

	return {row.user: set(parse_branches(row.get(BRANCHES_FIELD))) for row in before.get(PORTAL_USERS_FIELD)}


def validate_portal_branches(doc, method: str | None = None) -> None:
	seen: set[str] = set()
	shipping: set[str] | None = None
	saved: dict[str, set[str]] | None = None

	for row in doc.get(PORTAL_USERS_FIELD):
		if row.user in seen:
			frappe.throw(
				_("Row {0}: {1} is listed more than once. Pick all their branches on one row.").format(
					row.idx, frappe.bold(row.user)
				),
				title=_("Duplicate Portal User"),
			)
		seen.add(row.user)

		branches = parse_branches(row.get(BRANCHES_FIELD))
		if branches and row.get(ACCOUNT_ADMIN_FIELD):
			frappe.throw(
				_(
					"Row {0}: {1} is an account admin, so they must have every branch. Clear their branches or untick Account Admin."
				).format(row.idx, frappe.bold(row.user)),
				title=_("Account Admin Has Every Branch"),
			)

		if branches and shipping is None:
			shipping = {address.name for address in linked_addresses([doc.name], shipping_only=True)}
			saved = saved_branches(doc)

		kept = (saved or {}).get(row.user, set())
		unknown = [branch for branch in branches if branch not in (shipping or set()) and branch not in kept]
		if unknown:
			frappe.throw(
				_("Row {0}: {1} is not one of this customer's shipping addresses.").format(
					row.idx, ", ".join(frappe.bold(branch) for branch in unknown)
				),
				title=_("Not a Shipping Address"),
			)

		row.set(BRANCHES_FIELD, join_branches(branches) or None)


def branch_option(address: dict) -> dict:
	title = branch_title(address)
	return {
		"value": address.name,
		"label": _("{0} (Disabled)").format(title) if address.disabled else title,
		"description": ", ".join(part for part in (address.address_line1, address.city) if part),
	}


def selected_names(selected: list | str | None) -> list[str]:
	names = frappe.parse_json(selected) if isinstance(selected, str) else selected
	if not isinstance(names, list):
		return []

	return list(dict.fromkeys(cstr(name).strip() for name in names if cstr(name).strip()))[:MAX_SELECTED]


@frappe.whitelist()
def search_branches(
	customer: str, txt: str | None = None, selected: list | str | None = None
) -> ApiResponse[list]:
	frappe.has_permission(CUSTOMER, "read", doc=customer, throw=True)

	names = selected_names(selected)
	chosen = linked_addresses([customer], names=names) if names else []
	matches = linked_addresses(
		[customer], enabled_only=True, shipping_only=True, search=cstr(txt)[:140], limit=SEARCH_LIMIT
	)

	options = {address.name: branch_option(address) for address in [*chosen, *matches]}
	return ApiResponse.success(data=list(options.values()))
