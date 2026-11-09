# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint, flt, nowdate

from vuna_sourcing.api.transactions.customer_orders import ITEM_GROUP, PUBLISH_FIELD
from vuna_sourcing.utils import CUSTOMER

ITEM = "Item"
ITEM_DEFAULT = "Item Default"
ITEM_PRICE = "Item Price"
PRICE_LIST = "Price List"
PARTY_ACCOUNT = "Party Account"
COMPANY = "Company"
SOURCING_SETTINGS = "Sourcing Settings"
SELLING_SETTINGS = "Selling Settings"
ORDERS_ENABLED_FIELD = "allow_customer_sales_orders"
SELLING_PRICE_LIST_FIELD = "selling_price_list"
FALLBACK_PRICE_LIST = "Standard Selling"
PREVIEW_LIMIT = 20


def setup_portal_catalog(
	company: str | None = None,
	item_groups: list[str] | None = None,
	items: list[str] | None = None,
	price_list: str | None = None,
	default_rate: float | None = None,
	link_customers: int = 0,
	dry_run: int = 1,
) -> dict:
	dry_run = cint(dry_run)
	company = catalog_company(company)
	report = {
		"dry_run": bool(dry_run),
		"company": company,
		"settings": [],
		"groups_published": [],
		"items_published": [],
		"item_defaults_added": [],
		"prices_created": [],
		"unpriced_items": [],
		"customers_linked": [],
	}

	price_list = ensure_settings(price_list, report, dry_run)
	report["price_list"] = price_list

	groups = catalog_groups(item_groups)
	publish_groups(groups, report, dry_run)

	rows = eligible_items(groups, items)
	publish_items(rows, report, dry_run)
	ensure_item_defaults(rows, company, report, dry_run)
	ensure_prices(rows, price_list, default_rate, report, dry_run)

	if cint(link_customers):
		link_customers_to_company(company, report, dry_run)

	if not dry_run:
		frappe.db.commit()  # nosemgrep
		frappe.clear_cache()

	print_summary(report)
	return report


def catalog_company(company: str | None) -> str:
	company = company or frappe.defaults.get_global_default("company")
	if not company or not frappe.db.exists(COMPANY, company):
		frappe.throw(f"Company not found: {company!r}. Pass company='...'.")
	return company


def ensure_settings(price_list: str | None, report: dict, dry_run: int) -> str:
	if not cint(frappe.db.get_single_value(SOURCING_SETTINGS, ORDERS_ENABLED_FIELD)):
		report["settings"].append(f"{SOURCING_SETTINGS}: {ORDERS_ENABLED_FIELD} -> 1")
		if not dry_run:
			frappe.db.set_single_value(SOURCING_SETTINGS, ORDERS_ENABLED_FIELD, 1)

	current = frappe.db.get_single_value(SELLING_SETTINGS, SELLING_PRICE_LIST_FIELD)
	price_list = price_list or current or FALLBACK_PRICE_LIST

	state = frappe.db.get_value(PRICE_LIST, price_list, ["enabled", "selling"], as_dict=True)
	if not state:
		frappe.throw(f"Price List {price_list!r} does not exist. Create it first.")

	if not state.enabled or not state.selling:
		report["settings"].append(f"{PRICE_LIST} {price_list}: enabled=1, selling=1")
		if not dry_run:
			frappe.db.set_value(PRICE_LIST, price_list, {"enabled": 1, "selling": 1})

	if current != price_list:
		report["settings"].append(
			f"{SELLING_SETTINGS}: {SELLING_PRICE_LIST_FIELD} {current!r} -> {price_list!r}"
		)
		if not dry_run:
			frappe.db.set_single_value(SELLING_SETTINGS, SELLING_PRICE_LIST_FIELD, price_list)

	return price_list


def catalog_groups(item_groups: list[str] | None) -> list[str]:
	if not item_groups:
		return frappe.get_all(ITEM_GROUP, pluck="name", order_by="name asc")

	bounds = frappe.get_all(ITEM_GROUP, filters={"name": ("in", item_groups)}, fields=["name", "lft", "rgt"])
	missing = set(item_groups) - {row.name for row in bounds}
	if missing:
		frappe.throw(f"Item Group not found: {', '.join(sorted(missing))}")

	group = frappe.qb.DocType(ITEM_GROUP)
	within = None
	for row in bounds:
		branch = (group.lft >= row.lft) & (group.rgt <= row.rgt)
		within = branch if within is None else within | branch

	return sorted(set(frappe.qb.from_(group).select(group.name).where(within).run(pluck=True)))


def publish_groups(groups: list[str], report: dict, dry_run: int) -> None:
	unpublished = frappe.get_all(
		ITEM_GROUP, filters={"name": ("in", groups or [""]), PUBLISH_FIELD: 0}, pluck="name"
	)
	report["groups_published"] = unpublished
	if unpublished and not dry_run:
		mark_published(ITEM_GROUP, unpublished)


def eligible_items(groups: list[str], items: list[str] | None) -> list:
	filters = {
		"item_group": ("in", groups or [""]),
		"is_sales_item": 1,
		"disabled": 0,
		"has_variants": 0,
	}
	if items:
		filters["name"] = ("in", items)

	rows = frappe.get_all(
		ITEM,
		filters=filters,
		fields=["name", "stock_uom", "standard_rate", "valuation_rate", "end_of_life", PUBLISH_FIELD],
		order_by="name asc",
	)
	today = nowdate()
	return [row for row in rows if not row.end_of_life or str(row.end_of_life) > today]


def publish_items(rows: list, report: dict, dry_run: int) -> None:
	unpublished = [row.name for row in rows if not cint(row.get(PUBLISH_FIELD))]
	report["items_published"] = unpublished
	if unpublished and not dry_run:
		mark_published(ITEM, unpublished)


def mark_published(doctype: str, names: list[str]) -> None:
	table = frappe.qb.DocType(doctype)
	frappe.qb.update(table).set(table[PUBLISH_FIELD], 1).where(table.name.isin(names)).run()


def ensure_item_defaults(rows: list, company: str, report: dict, dry_run: int) -> None:
	codes = [row.name for row in rows]
	existing = frappe.get_all(
		ITEM_DEFAULT,
		filters={"parenttype": ITEM, "parent": ("in", codes or [""])},
		fields=["parent", "company", "idx"],
	)
	covered = {row.parent for row in existing if row.company == company}
	last_idx = {}
	for row in existing:
		last_idx[row.parent] = max(last_idx.get(row.parent, 0), cint(row.idx))

	missing = [code for code in codes if code not in covered]
	report["item_defaults_added"] = missing
	if dry_run:
		return

	for code in missing:
		frappe.get_doc(
			{
				"doctype": ITEM_DEFAULT,
				"parenttype": ITEM,
				"parentfield": "item_defaults",
				"parent": code,
				"company": company,
				"idx": last_idx.get(code, 0) + 1,
			}
		).db_insert()


def ensure_prices(rows: list, price_list: str, default_rate, report: dict, dry_run: int) -> None:
	priced = set(
		frappe.get_all(
			ITEM_PRICE,
			filters={
				"item_code": ("in", [row.name for row in rows] or [""]),
				"price_list": price_list,
				"customer": ("is", "not set"),
				"supplier": ("is", "not set"),
				"batch_no": ("is", "not set"),
			},
			pluck="item_code",
		)
	)

	for row in rows:
		if row.name in priced:
			continue

		rate = flt(default_rate) or flt(row.standard_rate) or flt(row.valuation_rate)
		if rate <= 0:
			report["unpriced_items"].append(row.name)
			continue

		report["prices_created"].append(f"{row.name} @ {rate}")
		if not dry_run:
			frappe.get_doc(
				{
					"doctype": ITEM_PRICE,
					"item_code": row.name,
					"price_list": price_list,
					"uom": row.stock_uom,
					"price_list_rate": rate,
				}
			).insert(ignore_permissions=True)


def link_customers_to_company(company: str, report: dict, dry_run: int) -> None:
	account = frappe.get_cached_value(COMPANY, company, "default_receivable_account")
	if not account:
		frappe.throw(f"Company {company!r} has no Default Receivable Account, so customers cannot be linked.")

	accounts = frappe.get_all(
		PARTY_ACCOUNT,
		filters={"parenttype": CUSTOMER, "parentfield": "accounts"},
		fields=["parent", "company", "idx"],
	)
	linked = {row.parent for row in accounts if row.company == company}
	last_idx = {}
	for row in accounts:
		last_idx[row.parent] = max(last_idx.get(row.parent, 0), cint(row.idx))

	missing = [
		name
		for name in frappe.get_all(CUSTOMER, filters={"disabled": 0}, pluck="name", order_by="name asc")
		if name not in linked
	]
	report["customers_linked"] = missing
	if dry_run:
		return

	for customer in missing:
		frappe.get_doc(
			{
				"doctype": PARTY_ACCOUNT,
				"parenttype": CUSTOMER,
				"parentfield": "accounts",
				"parent": customer,
				"company": company,
				"account": account,
				"idx": last_idx.get(customer, 0) + 1,
			}
		).db_insert()


def print_summary(report: dict) -> None:
	mode = "DRY RUN (nothing written)" if report["dry_run"] else "APPLIED"
	print(f"\nPortal catalog setup - {mode}")
	print(f"Company: {report['company']}   Price List: {report['price_list']}")
	for line in report["settings"]:
		print(f"  setting: {line}")
	for key in (
		"groups_published",
		"items_published",
		"item_defaults_added",
		"prices_created",
		"customers_linked",
		"unpriced_items",
	):
		values = report[key]
		print(f"{key}: {len(values)}")
		for value in values[:PREVIEW_LIMIT]:
			print(f"    {value}")
		if len(values) > PREVIEW_LIMIT:
			print(f"    ... and {len(values) - PREVIEW_LIMIT} more")
	if report["unpriced_items"]:
		print("\nUnpriced items stay hidden. Pass default_rate=... or set standard_rate on them.")
