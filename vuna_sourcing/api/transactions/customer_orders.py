# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Count, IfNull
from frappe.utils import cint, cstr, flt, getdate, nowdate, strip_html
from pypika.terms import ExistsCriterion

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.branches import (
	BRANCH_FIELD,
	branch_restrictions,
	customer_scope_filters,
	is_in_branch_scope,
	linked_addresses,
)
from vuna_sourcing.api.transactions.common import all_of, as_administrator, party_scope
from vuna_sourcing.utils import CUSTOMER

SALES_ORDER = "Sales Order"
FROM_PORTAL_FIELD = "created_from_portal"
PORTAL_STATUS_FIELD = "portal_submission_status"
ORDER_PENDING = "Pending"
ORDER_SUBMITTED = "Submitted"

PUBLISH_FIELD = "publish_on_portal"
ITEM_GROUP = "Item Group"
MAX_ORDER_LINES = 100
CATEGORY_PAGE = 24
MAX_CATEGORY_PAGE = 100
SEARCH_LENGTH = 140
PO_NUMBER_LENGTH = 140


def orders_enabled() -> bool:
	return bool(cint(frappe.db.get_single_value("Sourcing Settings", "allow_customer_sales_orders")))


def ensure_orders_enabled() -> None:
	if not orders_enabled():
		frappe.throw(_("Ordering on the portal is turned off."), frappe.PermissionError)


def ordering_customer(customer: str | None) -> str:
	if not customer:
		frappe.throw(_("Choose the customer account you are ordering for."))

	party_scope(CUSTOMER, customer)
	return customer


def order_companies(customer: str) -> list[str]:
	companies = frappe.get_all("Company", pluck="name", order_by="name asc")
	if len(companies) == 1:
		return companies

	return sorted(
		set(
			frappe.get_all(
				"Party Account",
				filters={
					"parenttype": CUSTOMER,
					"parentfield": "accounts",
					"parent": customer,
					"company": ("in", companies or [""]),
				},
				pluck="company",
			)
		)
	)


def can_order(customer: str | None) -> bool:
	return bool(customer) and orders_enabled() and bool(order_companies(customer))


def order_company(customer: str, company: str | None) -> str:
	companies = order_companies(customer)
	if not companies:
		frappe.throw(_("Your account is not set up for ordering yet. Please contact us."))

	if not company and len(companies) == 1:
		return companies[0]

	if company not in companies:
		frappe.throw(_("Choose a company you can order from."))

	return company


def orderable_items_query(company: str):
	item = frappe.qb.DocType("Item")
	default = frappe.qb.DocType("Item Default")
	group = frappe.qb.DocType(ITEM_GROUP)

	return (
		frappe.qb.from_(item)
		.join(default)
		.on((default.parent == item.name) & (default.parenttype == "Item") & (default.company == company))
		.join(group)
		.on((group.name == item.item_group) & (group[PUBLISH_FIELD] == 1))
		.where(item[PUBLISH_FIELD] == 1)
		.where(item.is_sales_item == 1)
		.where(item.disabled == 0)
		.where(item.has_variants == 0)
		.where(IfNull(item.end_of_life, "2500-12-31") > nowdate())
	), item


def orderable_items(company: str, item_codes: list[str]) -> dict[str, dict]:
	query, item = orderable_items_query(company)
	rows = (
		query.select(item.name, item.item_name, item.stock_uom)
		.where(item.name.isin(item_codes or [""]))
		.distinct()
		.run(as_dict=True)
	)
	return {row.name: row for row in rows}


def item_uoms(items: dict[str, dict]) -> dict[str, dict[str, float]]:
	uoms = {code: {item.stock_uom: 1.0} for code, item in items.items()}

	for row in frappe.get_all(
		"UOM Conversion Detail",
		filters={"parenttype": "Item", "parent": ("in", list(items) or [""])},
		fields=["parent", "uom", "conversion_factor"],
	):
		if flt(row.conversion_factor) > 0:
			uoms[row.parent].setdefault(row.uom, flt(row.conversion_factor))

	return uoms


def portal_price_list() -> str:
	price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
	if not price_list:
		frappe.throw(_("We cannot price orders for your account yet. Please contact us."))

	return price_list


def billing_currency(customer: str, company: str) -> str:
	return frappe.get_cached_value(CUSTOMER, customer, "default_currency") or frappe.get_cached_value(
		"Company", company, "default_currency"
	)


def exchange_rate(from_currency: str, to_currency: str, on_date, billing: str) -> float:
	from erpnext.setup.utils import get_exchange_rate

	rate = flt(get_exchange_rate(from_currency, to_currency, on_date, "for_selling"))
	if rate <= 0:
		frappe.throw(_("We cannot show prices in {0} yet. Please contact us.").format(billing))

	return rate


def applicable_prices(price_list: str, customer: str, on_date):
	price = frappe.qb.DocType("Item Price")
	return (
		frappe.qb.from_(price)
		.where(price.price_list == price_list)
		.where(
			(price.customer == customer)
			| ((IfNull(price.customer, "") == "") & (IfNull(price.supplier, "") == ""))
		)
		.where(IfNull(price.batch_no, "") == "")
		.where(IfNull(price.valid_from, "2000-01-01") <= on_date)
		.where(IfNull(price.valid_upto, "2500-12-31") >= on_date)
	), price


def item_prices(item_codes: list[str], price_list: str, customer: str, on_date) -> dict[str, list]:
	query, price = applicable_prices(price_list, customer, on_date)
	rows = (
		query.select(price.item_code, price.customer, price.uom, price.price_list_rate)
		.where(price.item_code.isin(item_codes or [""]))
		.orderby(IfNull(price.valid_from, "2000-01-01"), order=Order.desc)
		.orderby(price.creation, order=Order.desc)
	).run(as_dict=True)

	prices = {}
	for row in rows:
		prices.setdefault(row.item_code, []).append(row)
	return prices


def price_for(prices: list, uom: str, stock_uom: str, conversion_factor: float) -> float | None:
	for own_price in (True, False):
		candidates = [row for row in prices if bool(row.customer) == own_price]

		exact = next((row for row in candidates if row.uom == uom), None)
		if exact:
			return flt(exact.price_list_rate)

		per_stock_unit = next((row for row in candidates if not row.uom or row.uom == stock_uom), None)
		if per_stock_unit:
			return flt(per_stock_unit.price_list_rate) * flt(conversion_factor or 1)

	return None


def order_lines(items) -> dict[tuple[str, str], float]:
	lines = frappe.parse_json(items) if isinstance(items, str) else items
	if not isinstance(lines, list):
		frappe.throw(_("Add at least one item to your order."))

	merged = {}
	for line in lines:
		if not isinstance(line, dict):
			frappe.throw(_("Your order lines could not be read. Refresh the page and try again."))

		item_code = cstr(line.get("item_code")).strip()
		uom = cstr(line.get("uom")).strip()
		qty = flt(line.get("qty"))
		if not item_code:
			continue
		if not math.isfinite(qty) or qty <= 0:
			frappe.throw(_("Enter a quantity above zero for {0}.").format(item_code))

		merged[(item_code, uom)] = merged.get((item_code, uom), 0) + qty

	if not merged:
		frappe.throw(_("Add at least one item to your order."))
	if len(merged) > MAX_ORDER_LINES:
		frappe.throw(_("An order can have at most {0} lines.").format(MAX_ORDER_LINES))

	return merged


def delivery_date_of(value: str | None, required: bool = True):
	if not value:
		if required:
			frappe.throw(_("Choose the date you need this order delivered by."))
		return getdate(nowdate())

	try:
		date = getdate(value)
	except Exception:
		frappe.throw(_("Choose a valid delivery date."))

	if date < getdate(nowdate()):
		frappe.throw(_("The delivery date cannot be in the past."))

	return date


def customer_addresses(customer: str) -> list[dict]:
	addresses = linked_addresses([customer], enabled_only=True)
	allowed = branch_restrictions().get(customer)
	if allowed is None:
		return addresses

	return [address for address in addresses if address.name in allowed]


def address_option(address: dict) -> dict:
	return {
		"name": address.name,
		"title": address.address_title or address.address_type or address.name,
		"address_type": address.address_type,
		"lines": ", ".join(
			part
			for part in (
				address.address_line1,
				address.address_line2,
				address.city,
				address.state,
				address.country,
			)
			if part
		),
	}


def delivery_address(customer: str, chosen: str | None) -> str | None:
	names = [address.name for address in customer_addresses(customer)]
	if not names:
		if branch_restrictions().get(customer) is not None:
			frappe.throw(_("None of your branches can receive orders right now. Please contact us."))
		return None

	if not chosen and len(names) == 1:
		return names[0]

	if chosen not in names:
		frappe.throw(_("Choose where we should deliver this order."))

	return chosen


def validate_po_number(doc) -> None:
	if not doc.po_no or cint(
		frappe.db.get_single_value("Selling Settings", "allow_against_multiple_purchase_orders")
	):
		return

	used_on = frappe.db.get_value(
		SALES_ORDER,
		{
			"customer": doc.customer,
			"po_no": doc.po_no,
			"docstatus": ("<", 2),
			"name": ("!=", doc.name or ""),
		},
		"name",
	)
	if not used_on:
		return

	if not is_in_branch_scope(doc.customer, frappe.db.get_value(SALES_ORDER, used_on, BRANCH_FIELD)):
		frappe.throw(
			_("PO number {0} is already used on another order. Use a different PO number.").format(doc.po_no)
		)

	frappe.throw(
		_("You already used PO number {0} on order {1}. Use a different PO number.").format(
			doc.po_no, used_on
		)
	)


def own_portal_order(name: str, customer: str) -> str:
	mine = frappe.db.get_value(
		SALES_ORDER,
		all_of(customer_scope_filters(SALES_ORDER, [customer]), {"name": name, FROM_PORTAL_FIELD: 1}),
		"name",
	)
	if not mine:
		frappe.throw(_("This order does not belong to you."), frappe.PermissionError)

	return mine


def locked_portal_order(name: str, customer: str):
	doc = frappe.get_doc(SALES_ORDER, own_portal_order(name, customer), for_update=True)
	if (
		doc.customer != customer
		or not doc.get(FROM_PORTAL_FIELD)
		or not is_in_branch_scope(customer, doc.get(BRANCH_FIELD))
	):
		frappe.throw(_("This order does not belong to you."), frappe.PermissionError)

	return doc


def locked_draft(name: str, customer: str):
	doc = locked_portal_order(name, customer)
	if doc.docstatus != 0 or doc.get(PORTAL_STATUS_FIELD) != ORDER_PENDING:
		frappe.throw(_("This order has been sent, so it can no longer be changed."))

	return doc


def apply_prices(doc, customer: str) -> None:
	prices = item_prices(
		[row.item_code for row in doc.items], doc.selling_price_list, customer, doc.transaction_date
	)
	to_order_currency = exchange_rate(
		frappe.get_cached_value("Price List", doc.selling_price_list, "currency"),
		doc.currency,
		doc.transaction_date,
		doc.currency,
	)

	unpriced = []
	for row in doc.items:
		price = price_for(prices.get(row.item_code, []), row.uom, row.stock_uom, row.conversion_factor)
		if not price or price <= 0:
			unpriced.append(row.item_name or row.item_code)
			continue

		rate = flt(price * to_order_currency, row.precision("rate"))
		row.update(
			{
				"price_list_rate": rate,
				"rate": rate,
				"discount_percentage": 0,
				"discount_amount": 0,
				"margin_type": None,
				"margin_rate_or_amount": 0,
				"pricing_rules": None,
			}
		)

	if unpriced:
		frappe.throw(
			_("We do not have a price for {0} yet. Remove it from your order or contact us.").format(
				", ".join(unpriced)
			)
		)


def fill_order(
	doc,
	customer: str,
	company: str,
	items,
	delivery_date,
	shipping_address: str | None,
	po_no: str | None,
) -> None:
	lines = order_lines(items)
	codes = sorted({item_code for item_code, _uom in lines})
	available = orderable_items(company, codes)

	missing = [code for code in codes if code not in available]
	if missing:
		frappe.throw(_("These items cannot be ordered: {0}").format(", ".join(missing)))

	uoms = item_uoms(available)
	currency = billing_currency(customer, company)
	exchange_rate(
		currency, frappe.get_cached_value("Company", company, "default_currency"), nowdate(), currency
	)

	doc.update(
		{
			"customer": customer,
			"company": company,
			"order_type": "Sales",
			"transaction_date": nowdate(),
			"delivery_date": delivery_date,
			"po_no": cstr(po_no).strip()[:PO_NUMBER_LENGTH] or None,
			"shipping_address_name": shipping_address,
			"selling_price_list": portal_price_list(),
			"currency": currency,
			"ignore_pricing_rule": 1,
			FROM_PORTAL_FIELD: 1,
		}
	)
	validate_po_number(doc)
	doc.set("items", [])

	for (item_code, uom), qty in lines.items():
		uom = uom or available[item_code].stock_uom
		if uom not in uoms[item_code]:
			frappe.throw(_("{0} cannot be ordered in {1}.").format(available[item_code].item_name, uom))

		doc.append(
			"items",
			{
				"item_code": item_code,
				"uom": uom,
				"conversion_factor": uoms[item_code][uom],
				"qty": qty,
				"delivery_date": delivery_date,
			},
		)

	doc.flags.ignore_permissions = True
	with as_administrator():
		doc.set_missing_values()
		apply_prices(doc, customer)
		doc.calculate_taxes_and_totals()


def customised_requirements(doctype: str) -> set[str]:
	custom = {
		df.fieldname
		for df in frappe.get_meta(doctype).fields
		if df.reqd and getattr(df, "is_custom_field", False)
	}
	set_by_property = frappe.get_all(
		"Property Setter",
		filters={"doc_type": doctype, "property": "reqd", "value": "1"},
		pluck="field_name",
	)
	return custom | set(set_by_property)


def validate_portal_mandatory(doc) -> None:
	skipped = {}
	missing = []

	for row in (doc, *doc.get_all_children()):
		if row.doctype not in skipped:
			skipped[row.doctype] = customised_requirements(row.doctype)

		missing.extend(
			strip_html(message)
			for fieldname, message in row._get_missing_mandatory_fields()
			if fieldname not in skipped[row.doctype]
		)

	if missing:
		frappe.throw("<br>".join(missing), frappe.MandatoryError)


def write_order(doc, status: str) -> None:
	if doc.is_new():
		doc.owner = frappe.session.user

	doc.set(PORTAL_STATUS_FIELD, status)
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	with as_administrator():
		doc.save()
		validate_portal_mandatory(doc)


def prepared_order(
	customer: str | None,
	items,
	company: str | None,
	name: str | None,
	delivery_date: str | None,
	shipping_address: str | None,
	po_no: str | None,
):
	ensure_orders_enabled()
	customer = ordering_customer(customer)

	if name:
		doc = locked_draft(name, customer)
		if company and company != doc.company:
			frappe.throw(_("To order from another company, start a new order."))
		company = doc.company
	else:
		doc = frappe.new_doc(SALES_ORDER)

	fill_order(
		doc,
		customer,
		order_company(customer, company),
		items,
		delivery_date_of(delivery_date),
		delivery_address(customer, shipping_address),
		po_no,
	)
	return doc


def order_view(doc) -> dict:
	images = dict(
		frappe.get_all(
			"Item",
			filters={"name": ("in", [row.item_code for row in doc.items] or [""])},
			fields=["name", "image"],
			as_list=True,
		)
	)

	uoms = item_uoms({row.item_code: frappe._dict(stock_uom=row.stock_uom) for row in doc.items})

	return {
		"name": None if doc.is_new() else doc.name,
		"company": doc.company,
		"currency": doc.currency,
		"delivery_date": doc.delivery_date,
		"po_no": doc.po_no,
		"shipping_address": doc.shipping_address_name,
		"status": doc.get(PORTAL_STATUS_FIELD),
		"items": [
			{
				"item_code": row.item_code,
				"item_name": row.item_name or row.item_code,
				"image": images.get(row.item_code),
				"qty": row.qty,
				"uom": row.uom,
				"uoms": [
					{"uom": uom, "conversion_factor": factor} for uom, factor in uoms[row.item_code].items()
				],
				"rate": row.rate,
				"amount": row.amount,
			}
			for row in doc.items
		],
		"net_total": doc.net_total,
		"total_taxes": doc.total_taxes_and_charges,
		"grand_total": doc.grand_total,
	}


@frappe.whitelist()
def get_order_form(customer: str, name: str | None = None) -> ApiResponse[dict]:
	customer = ordering_customer(customer)
	if not orders_enabled():
		return ApiResponse.error(_("Ordering on the portal is turned off."))

	companies = order_companies(customer)
	if not companies:
		return ApiResponse.error(_("Your account is not set up for ordering yet. Please contact us."))

	order = None
	if name:
		draft = frappe.get_doc(SALES_ORDER, own_portal_order(name, customer))
		if draft.docstatus != 0 or draft.get(PORTAL_STATUS_FIELD) != ORDER_PENDING:
			return ApiResponse.error(_("This order has been sent, so it can no longer be changed."))
		order = order_view(draft)

	return ApiResponse.success(
		data={
			"companies": companies,
			"addresses": [address_option(address) for address in customer_addresses(customer)],
			"today": nowdate(),
			"order": order,
		}
	)


def priced_items_query(company: str, price_list: str, customer: str):
	priced, price = applicable_prices(price_list, customer, nowdate())
	query, item = orderable_items_query(company)
	return query.where(ExistsCriterion(priced.select(price.name).where(price.item_code == item.name))), item


@frappe.whitelist()
def get_order_categories(
	customer: str,
	company: str | None = None,
	search: str | None = None,
	start: int = 0,
	limit: int = CATEGORY_PAGE,
) -> ApiResponse[dict]:
	ensure_orders_enabled()
	customer = ordering_customer(customer)
	company = order_company(customer, company)
	start = max(cint(start), 0)
	limit = min(max(cint(limit), 1), MAX_CATEGORY_PAGE)
	search = cstr(search).strip()[:SEARCH_LENGTH]
	price_list = portal_price_list()

	query, item = priced_items_query(company, price_list, customer)
	query = (
		query.select(item.item_group, Count(item.name).distinct().as_("item_count"))
		.where(IfNull(item.item_group, "") != "")
		.groupby(item.item_group)
		.orderby(item.item_group)
	)
	if search:
		query = query.where(item.item_group.like(f"%{search}%"))

	rows = query.limit(limit + 1).offset(start).run(as_dict=True)

	all_items = None
	if not start and not search:
		count_query, counted = priced_items_query(company, price_list, customer)
		all_items = count_query.select(Count(counted.name).distinct()).run()[0][0]

	return ApiResponse.success(
		data={
			"rows": [{"name": row.item_group, "count": row.item_count} for row in rows[:limit]],
			"has_more": len(rows) > limit,
			"all_items": all_items,
		}
	)


@frappe.whitelist()
def get_orderable_items(
	customer: str,
	company: str | None = None,
	search: str | None = None,
	item_group: str | None = None,
	start: int = 0,
	limit: int = 20,
) -> ApiResponse[dict]:
	ensure_orders_enabled()
	customer = ordering_customer(customer)
	company = order_company(customer, company)
	start = max(cint(start), 0)
	limit = min(max(cint(limit), 1), 50)

	price_list = portal_price_list()
	query, item = priced_items_query(company, price_list, customer)
	query = query.select(
		item.name, item.item_name, item.description, item.image, item.stock_uom, item.item_group
	).distinct()

	search = cstr(search).strip()[:SEARCH_LENGTH]
	if search:
		pattern = f"%{search}%"
		query = query.where(item.name.like(pattern) | item.item_name.like(pattern))

	if item_group:
		query = query.where(item.item_group == item_group)

	rows = query.orderby(item.item_name).limit(limit + 1).offset(start).run(as_dict=True)
	page = rows[:limit]

	available = {row.name: row for row in page}
	uoms = item_uoms(available)
	prices = item_prices(list(available), price_list, customer, nowdate())
	currency = billing_currency(customer, company)
	to_currency = exchange_rate(
		frappe.get_cached_value("Price List", price_list, "currency"), currency, nowdate(), currency
	)

	def listed_price(row) -> tuple[str, float | None]:
		factors = uoms[row.name]
		for uom in sorted(factors, key=lambda uom: uom != row.stock_uom):
			rate = price_for(prices.get(row.name, []), uom, row.stock_uom, factors[uom])
			if rate:
				return uom, flt(rate * to_currency, 2)
		return row.stock_uom, None

	return ApiResponse.success(
		data={
			"currency": currency,
			"has_more": len(rows) > limit,
			"rows": [
				{
					"item_code": row.name,
					"item_name": row.item_name or row.name,
					"description": strip_html(row.description or "").strip() or None,
					"image": row.image,
					"item_group": row.item_group,
					"stock_uom": row.stock_uom,
					"uoms": [
						{"uom": uom, "conversion_factor": factor} for uom, factor in uoms[row.name].items()
					],
					"uom": uom,
					"rate": rate,
				}
				for row, (uom, rate) in ((row, listed_price(row)) for row in page)
			],
		}
	)


@frappe.whitelist(methods=["POST"])
def price_order(
	customer: str,
	items: list | str | None = None,
	company: str | None = None,
	delivery_date: str | None = None,
	shipping_address: str | None = None,
) -> ApiResponse[dict]:
	ensure_orders_enabled()
	customer = ordering_customer(customer)

	doc = frappe.new_doc(SALES_ORDER)
	fill_order(
		doc,
		customer,
		order_company(customer, company),
		items,
		delivery_date_of(delivery_date, required=False),
		delivery_address(customer, shipping_address) if shipping_address else None,
		None,
	)
	return ApiResponse.success(data=order_view(doc))


@frappe.whitelist(methods=["POST"])
def save_order(
	customer: str,
	items: list | str | None = None,
	company: str | None = None,
	name: str | None = None,
	delivery_date: str | None = None,
	shipping_address: str | None = None,
	po_no: str | None = None,
) -> ApiResponse[dict]:
	doc = prepared_order(customer, items, company, name, delivery_date, shipping_address, po_no)
	write_order(doc, ORDER_PENDING)
	return ApiResponse.success(_("Draft saved."), order_view(doc))


@frappe.whitelist(methods=["POST"])
def submit_order(
	customer: str,
	items: list | str | None = None,
	company: str | None = None,
	name: str | None = None,
	delivery_date: str | None = None,
	shipping_address: str | None = None,
	po_no: str | None = None,
) -> ApiResponse[dict]:
	doc = prepared_order(customer, items, company, name, delivery_date, shipping_address, po_no)
	write_order(doc, ORDER_SUBMITTED)
	return ApiResponse.success(_("Order sent. We will confirm it shortly."), order_view(doc))


def zero_totals(doc) -> None:
	for row in (doc, *doc.get("taxes", [])):
		for df in row.meta.fields:
			if df.fieldtype == "Currency":
				row.set(df.fieldname, 0)

	doc.update({"total_qty": 0, "total_net_weight": 0, "in_words": "", "base_in_words": ""})


@frappe.whitelist(methods=["POST"])
def clear_order(customer: str, name: str) -> ApiResponse[dict]:
	ensure_orders_enabled()
	doc = locked_draft(name, ordering_customer(customer))

	doc.set("items", [])
	zero_totals(doc)
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	with as_administrator():
		doc.save()

	return ApiResponse.success(_("Cart cleared."), order_view(doc))


@frappe.whitelist(methods=["POST"])
def delete_order(customer: str, name: str) -> ApiResponse[None]:
	doc = locked_draft(name, ordering_customer(customer))
	frappe.delete_doc(SALES_ORDER, doc.name, ignore_permissions=True)
	return ApiResponse.success(_("Draft deleted."))


@frappe.whitelist(methods=["POST"])
def withdraw_order(customer: str, name: str) -> ApiResponse[dict]:
	doc = locked_portal_order(name, ordering_customer(customer))

	if doc.docstatus != 0:
		frappe.throw(_("This order has been confirmed, so it can no longer be withdrawn."))
	if doc.get(PORTAL_STATUS_FIELD) != ORDER_SUBMITTED:
		frappe.throw(_("This order has not been sent yet."))

	with as_administrator():
		doc.db_set(PORTAL_STATUS_FIELD, ORDER_PENDING)
		doc.add_comment("Info", _("Withdrawn by the customer on the portal."))

	return ApiResponse.success(_("Order withdrawn. It is back in your drafts."), {"name": doc.name})
