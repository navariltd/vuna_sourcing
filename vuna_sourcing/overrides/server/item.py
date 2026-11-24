# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.permissions import get_doctype_roles
from frappe.utils import cstr, escape_html, flt, formatdate, getdate, nowdate

from vuna_sourcing.api.portal import PARTY_ROLE
from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.customer_orders import (
	ALLOWED_COMPANIES_FIELD,
	COMPANY,
	DEFAULT_COMPANY_FIELD,
	ITEM,
	ITEM_GROUP,
	PUBLISH_FIELD,
	RESTRICTED_FIELD,
	SALES_ORDER,
	SETTINGS,
	order_companies,
	orders_enabled,
	priced_items_query,
)
from vuna_sourcing.api.transactions.rights import CREATE
from vuna_sourcing.utils import CUSTOMER

ITEM_PRICE = "Item Price"
SELLING_SETTINGS = "Selling Settings"
DEFAULT_PRICE_LIST_FIELD = "selling_price_list"
ORDERS_FIELD = "allow_customer_sales_orders"

PASSED = "passed"
FAILED = "failed"
SKIPPED = "skipped"

SET_FIELD = "set_field"
SET_VALUE = "set_value"
OPEN = "open"
NEW = "new"
FOCUS = "focus"
VARIANTS = "variants"

PRICE_FIELDS = (
	"name",
	"customer",
	"supplier",
	"batch_no",
	"valid_from",
	"valid_upto",
	"price_list_rate",
	"currency",
	"uom",
)


def strong(value) -> str:
	return frappe.bold(escape_html(cstr(value)))


def listed(values) -> str:
	return escape_html(", ".join(cstr(value) for value in values))


def check(label: str, status: str, detail: str, action: dict | None = None) -> dict:
	return {"label": label, "status": status, "detail": detail, "action": action}


def passed(label: str, detail: str) -> dict:
	return check(label, PASSED, detail)


def failed(label: str, detail: str, action: dict | None = None) -> dict:
	return check(label, FAILED, detail, action)


def skipped(label: str, detail: str) -> dict:
	return check(label, SKIPPED, detail)


def fix(kind: str, label: str, **target) -> dict:
	return {"kind": kind, "label": label, **target}


def portal_checks(price_list: str | None, company: str | None, chose_company: bool) -> list[dict]:
	orders_on = orders_enabled()
	customers_can_order = PARTY_ROLE[CUSTOMER] in get_doctype_roles(SALES_ORDER, CREATE)

	return [
		passed(_("Customer ordering is on"), _("Customers can place orders on the portal."))
		if orders_on
		else failed(
			_("Customer ordering is off"),
			_("Turn on Allow Customer Sales Orders in Sourcing Settings. Until then no item is offered."),
			fix(OPEN, _("Open Sourcing Settings"), doctype=SETTINGS, name=SETTINGS),
		),
		passed(_("Customers may create orders"), _("The Customer role has Create on Sales Order."))
		if customers_can_order
		else failed(
			_("Customers may not create orders"),
			_("Give the Customer role Create on Sales Order in Role Permission Manager."),
			fix(OPEN, _("Open Role Permissions"), route=["permission-manager", SALES_ORDER]),
		),
		passed(_("Portal price list is set"), _("Prices come from {0}.").format(strong(price_list)))
		if price_list
		else failed(
			_("No portal price list"),
			_("Set the Default Price List in Selling Settings. The portal prices every item from it."),
			fix(OPEN, _("Open Selling Settings"), doctype=SELLING_SETTINGS, name=SELLING_SETTINGS),
		),
		passed(
			_("Checking for {0}").format(strong(company)),
			_("The company you picked above.")
			if chose_company
			else _("The Default Ordering Company in Sourcing Settings."),
		)
		if company
		else failed(
			_("No company to order from"),
			_(
				"Set a Default Ordering Company in Sourcing Settings, or pick a company above to check against it."
			),
			fix(OPEN, _("Open Sourcing Settings"), doctype=SETTINGS, name=SETTINGS),
		),
	]


def item_checks(item, end_of_life) -> list[dict]:
	checks = [
		passed(_("Sell on Sourcing Portal is ticked"), _("The item is offered on the portal."))
		if item.get(PUBLISH_FIELD)
		else failed(
			_("Sell on Sourcing Portal is not ticked"),
			_("Only items with this ticked are offered to customers."),
			fix(SET_FIELD, _("Tick it"), field=PUBLISH_FIELD, value=1),
		),
		passed(_("Is Sales Item is ticked"), _("The item can be sold."))
		if item.is_sales_item
		else failed(
			_("Is Sales Item is not ticked"),
			_("Items that cannot be sold are never offered."),
			fix(SET_FIELD, _("Tick it"), field="is_sales_item", value=1),
		),
		failed(
			_("The item is disabled"),
			_("Disabled items are never offered."),
			fix(SET_FIELD, _("Enable it"), field="disabled", value=0),
		)
		if item.disabled
		else passed(_("The item is enabled"), _("It is not disabled.")),
		failed(
			_("This is a template item"),
			_("Templates are never offered. Customers order its variants, so publish and price those."),
			fix(VARIANTS, _("Show variants"), item=item.name),
		)
		if item.has_variants
		else passed(_("Not a template"), _("Customers order this item directly.")),
	]

	if end_of_life and getdate(end_of_life) <= getdate(nowdate()):
		checks.append(
			failed(
				_("End of life has passed"),
				_("It reached its end of life on {0}.").format(formatdate(end_of_life)),
				fix(SET_FIELD, _("Clear the date"), field="end_of_life", value=None),
			)
		)
	else:
		checks.append(
			passed(
				_("Not at end of life"),
				_("Offered until {0}.").format(formatdate(end_of_life)) if end_of_life else _("No end date."),
			)
		)

	return checks


def group_check(item_group: str | None) -> dict:
	if not item_group:
		return failed(
			_("No item group"),
			_("Set an Item Group that is shown on the portal."),
			fix(FOCUS, _("Set the group"), field="item_group"),
		)

	if frappe.db.get_value(ITEM_GROUP, item_group, PUBLISH_FIELD):
		return passed(
			_("{0} is shown on the portal").format(strong(item_group)),
			_("Its items are listed under this category."),
		)

	return failed(
		_("{0} is not shown on the portal").format(strong(item_group)),
		_(
			"Tick Show on Sourcing Portal on the item group. This shows every published item in the group, not just this one."
		),
		fix(
			SET_VALUE,
			_("Show the group"),
			doctype=ITEM_GROUP,
			name=item_group,
			field=PUBLISH_FIELD,
			value=1,
		),
	)


def company_check(item, company: str | None) -> dict:
	label = _("Company restriction")
	if not item.get(RESTRICTED_FIELD):
		return passed(label, _("Not restricted, so it is offered for every company."))

	allowed = [row.company for row in item.get(ALLOWED_COMPANIES_FIELD)]
	if not company:
		return skipped(label, _("Restricted to {0}. Pick a company to check it.").format(listed(allowed)))
	if company in allowed:
		return passed(label, _("{0} is one of its allowed companies.").format(strong(company)))

	return failed(
		label,
		_("Restricted to {0}, so it is hidden when ordering from {1}.").format(
			listed(allowed) or _("no company"), strong(company)
		),
		fix(FOCUS, _("Edit allowed companies"), field=ALLOWED_COMPANIES_FIELD),
	)


def price_problem(row, customer: str | None, today) -> str | None:
	if row.customer and row.customer != customer:
		return _("for customer {0} only").format(escape_html(row.customer))
	if row.supplier:
		return _("a buying price for {0}").format(escape_html(row.supplier))
	if row.batch_no:
		return _("for batch {0} only").format(escape_html(row.batch_no))
	if row.valid_from and getdate(row.valid_from) > today:
		return _("starts on {0}").format(formatdate(row.valid_from))
	if row.valid_upto and getdate(row.valid_upto) < today:
		return _("ended on {0}").format(formatdate(row.valid_upto))
	return None


def price_check(item_code: str, price_list: str | None, customer: str | None) -> dict:
	label = _("Price")
	if not price_list:
		return skipped(label, _("Set a portal price list first."))

	add_price = fix(
		NEW,
		_("Add a price"),
		doctype=ITEM_PRICE,
		values={"item_code": item_code, "price_list": price_list, "selling": 1},
	)
	today = getdate(nowdate())
	rows = frappe.get_all(
		ITEM_PRICE,
		filters={"item_code": item_code, "price_list": price_list},
		fields=list(PRICE_FIELDS),
		order_by="valid_from desc, creation desc",
	)
	usable = [row for row in rows if not price_problem(row, customer, today)]

	if usable:
		price = next((row for row in usable if row.customer), usable[0])
		return passed(
			label,
			_("{0} per {1} on {2}{3}.").format(
				strong(frappe.format_value(flt(price.price_list_rate), currency=price.currency)),
				escape_html(price.uom or _("unit")),
				escape_html(price_list),
				_(" for {0}").format(escape_html(price.customer)) if price.customer else "",
			),
		)

	if rows:
		reasons = "; ".join(sorted({price_problem(row, customer, today) for row in rows}))
		return failed(
			label,
			_("{0} has prices for this item, but none can be used today: {1}.").format(
				strong(price_list), reasons
			),
			add_price,
		)

	elsewhere = frappe.get_all(
		ITEM_PRICE,
		filters={"item_code": item_code, "selling": 1, "price_list": ("!=", price_list)},
		pluck="price_list",
		distinct=True,
		limit=3,
	)
	return failed(
		label,
		_("There is no price on {0}, the portal price list.").format(strong(price_list))
		+ (
			_(" It is priced on {0}, which the portal does not use.").format(listed(elsewhere))
			if elsewhere
			else ""
		),
		add_price,
	)


def customer_check(customer: str | None, company: str | None) -> dict:
	label = _("Customer can order")
	if not customer:
		return skipped(label, _("Pick a customer to check their companies and own prices."))
	if not company:
		return skipped(label, _("Pick a company to check this customer."))

	companies = order_companies(customer)
	if company in companies:
		return passed(label, _("{0} can order from {1}.").format(strong(customer), strong(company)))

	return failed(
		label,
		_("{0} cannot order from {1}. They can order from: {2}.").format(
			strong(customer), strong(company), listed(companies) or _("no company")
		),
		fix(OPEN, _("Open customer"), doctype=CUSTOMER, name=customer),
	)


def offered_on_portal(item_code: str, company: str, price_list: str, customer: str | None) -> bool:
	query, item = priced_items_query(company, price_list, customer or "")
	return bool(query.select(item.name).where(item.name == item_code).limit(1).run())


@frappe.whitelist()
def get_portal_visibility(
	item: str, company: str | None = None, customer: str | None = None
) -> ApiResponse[dict]:
	frappe.has_permission(ITEM, "read", doc=item, throw=True)
	if company:
		frappe.has_permission(COMPANY, "read", doc=company, throw=True)
	if customer:
		frappe.has_permission(CUSTOMER, "read", doc=customer, throw=True)

	doc = frappe.get_doc(ITEM, item)
	chose_company = bool(company)
	company = company or frappe.db.get_single_value(SETTINGS, DEFAULT_COMPANY_FIELD) or None
	price_list = frappe.db.get_single_value(SELLING_SETTINGS, DEFAULT_PRICE_LIST_FIELD) or None

	sections = [
		{"label": _("Portal"), "checks": portal_checks(price_list, company, chose_company)},
		{"label": _("This item"), "checks": item_checks(doc, doc.end_of_life)},
		{"label": _("Category"), "checks": [group_check(doc.item_group)]},
		{"label": _("Company"), "checks": [company_check(doc, company)]},
		{"label": _("Price"), "checks": [price_check(doc.name, price_list, customer)]},
		{"label": _("Customer"), "checks": [customer_check(customer, company)]},
	]
	blocking = sum(check["status"] == FAILED for section in sections for check in section["checks"])
	shown = (
		orders_enabled()
		and bool(company and price_list)
		and offered_on_portal(doc.name, company, price_list, customer)
		and not (customer and company not in order_companies(customer))
	)

	return ApiResponse.success(
		data={
			"item": doc.name,
			"item_name": doc.item_name,
			"company": company,
			"customer": customer,
			"shown": bool(shown) and blocking == 0,
			"blocking": blocking,
			"sections": sections,
		}
	)
