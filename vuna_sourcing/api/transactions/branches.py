# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import Order

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.utils import CUSTOMER

PORTAL_USER = "Portal User"
ADDRESS = "Address"
DYNAMIC_LINK = "Dynamic Link"
BRANCHES_FIELD = "branches"
ACCOUNT_ADMIN_FIELD = "is_account_admin"
BRANCH_FIELD = "shipping_address_name"
BRANCH_SEPARATOR = "\n"
MAX_BRANCH_FILTER = 50
SHIPPING = "Shipping"


def parse_branches(value: str | None) -> list[str]:
	return list(dict.fromkeys(part.strip() for part in (value or "").splitlines() if part.strip()))


def join_branches(branches: list[str]) -> str:
	return BRANCH_SEPARATOR.join(branches)


def branch_restrictions(user: str | None = None) -> dict[str, list[str]]:
	user = user or frappe.session.user
	assigned: dict[str, list[str]] = {}
	unrestricted: set[str] = set()

	for row in frappe.get_all(
		PORTAL_USER,
		filters={"parenttype": CUSTOMER, "user": user},
		fields=["parent", BRANCHES_FIELD],
	):
		branches = parse_branches(row.get(BRANCHES_FIELD))
		if branches:
			assigned.setdefault(row.parent, []).extend(branches)
		else:
			unrestricted.add(row.parent)

	return {
		customer: list(dict.fromkeys(branches))
		for customer, branches in assigned.items()
		if customer not in unrestricted
	}


def is_shipping(address: dict) -> bool:
	return address.get("address_type") == SHIPPING or bool(address.get("is_shipping_address"))


def linked_addresses(
	customers: list[str],
	enabled_only: bool = False,
	shipping_only: bool = False,
	search: str | None = None,
	limit: int | None = None,
	names: list[str] | None = None,
) -> list[dict]:
	if not customers:
		return []

	address = frappe.qb.DocType(ADDRESS)
	link = frappe.qb.DocType(DYNAMIC_LINK)
	query = (
		frappe.qb.from_(address)
		.join(link)
		.on((link.parent == address.name) & (link.parenttype == ADDRESS))
		.select(
			link.link_name.as_("customer"),
			address.name,
			address.address_title,
			address.address_type,
			address.address_line1,
			address.address_line2,
			address.city,
			address.state,
			address.country,
			address.is_primary_address,
			address.is_shipping_address,
			address.disabled,
		)
		.where(link.link_doctype == CUSTOMER)
		.where(link.link_name.isin(customers))
		.orderby(address.is_shipping_address, order=Order.desc)
		.orderby(address.is_primary_address, order=Order.desc)
		.orderby(address.creation, order=Order.asc)
	)
	if enabled_only:
		query = query.where(address.disabled == 0)
	if shipping_only:
		query = query.where((address.address_type == SHIPPING) | (address.is_shipping_address == 1))
	if search and search.strip():
		pattern = f"%{search.strip()}%"
		query = query.where(
			address.address_title.like(pattern)
			| address.name.like(pattern)
			| address.address_line1.like(pattern)
			| address.city.like(pattern)
		)
	if names:
		query = query.where(address.name.isin(names))
	if limit:
		query = query.limit(limit)

	return query.run(as_dict=True)


def branch_title(address: dict) -> str:
	return address.get("address_title") or address.get("address_type") or address.get("name")


def party_branches(customers: list[str], user: str | None = None) -> dict[str, dict]:
	restricted = branch_restrictions(user)
	addresses: dict[str, list[dict]] = {}
	for address in linked_addresses(customers):
		addresses.setdefault(address.customer, []).append(address)

	scoped = {}
	for customer in customers:
		linked = addresses.get(customer, [])
		allowed = restricted.get(customer)
		if allowed is None:
			branches = [
				{"name": address.name, "title": branch_title(address)}
				for address in linked
				if is_shipping(address)
			]
		else:
			titles = {address.name: branch_title(address) for address in linked}
			branches = [{"name": name, "title": titles.get(name, name)} for name in allowed]

		scoped[customer] = {"all_branches": allowed is None, "branches": branches}

	return scoped


@frappe.whitelist()
def get_branches(customer: str) -> ApiResponse[dict]:
	from vuna_sourcing.api.portal import check_party_access

	check_party_access(CUSTOMER, customer)
	return ApiResponse.success(data=party_branches([customer])[customer])


def has_all_branches(customer: str, user: str | None = None) -> bool:
	return customer not in branch_restrictions(user)


def is_in_branch_scope(customer: str, branch: str | None, user: str | None = None) -> bool:
	allowed = branch_restrictions(user).get(customer)
	return allowed is None or (bool(branch) and branch in allowed)


def customer_scope_filters(
	doctype: str,
	customers: list[str],
	party_field: str = "customer",
	branches: list[str] | None = None,
	user: str | None = None,
) -> list:
	filters: list = [{party_field: ("in", customers or [""])}]

	restricted = branch_restrictions(user)
	limited = {customer: restricted[customer] for customer in customers if customer in restricted}
	if limited:
		table = frappe.qb.DocType(doctype)
		party = table[party_field]
		criterion = party.isin([customer for customer in customers if customer not in limited] or [""])
		for customer, allowed in limited.items():
			criterion |= (party == customer) & table[BRANCH_FIELD].isin(allowed)
		filters.append(criterion)

	if branches:
		filters.append({BRANCH_FIELD: ("in", branches)})

	return filters


def requested_branches(customers: list[str], branches: list | str | None) -> list[str]:
	if not branches:
		return []

	if isinstance(branches, str):
		branches = frappe.parse_json(branches)

	if not isinstance(branches, list) or len(branches) > MAX_BRANCH_FILTER:
		frappe.throw(_("Choose up to {0} branches.").format(MAX_BRANCH_FILTER))

	chosen = list(dict.fromkeys(str(branch).strip() for branch in branches if str(branch).strip()))
	if not chosen:
		return []

	selectable = {
		branch["name"] for scope in party_branches(customers).values() for branch in scope["branches"]
	}
	if any(branch not in selectable for branch in chosen):
		frappe.throw(_("You do not have access to one of the branches you picked."), frappe.PermissionError)

	return chosen
