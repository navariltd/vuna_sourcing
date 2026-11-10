# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from erpnext.selling.doctype.customer.customer import get_credit_limit, get_customer_outstanding
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.branches import branch_restrictions
from vuna_sourcing.api.transactions.common import party_scope
from vuna_sourcing.api.transactions.customer_orders import order_companies
from vuna_sourcing.utils import CUSTOMER

SHOW_FIELD = "show_customer_credit_limits"
CREDIT_LIMIT = "Customer Credit Limit"
NEAR_LIMIT_PERCENT = 90

OVER = "over"
NEAR = "near"
WITHIN = "within"
STATE_ORDER = {OVER: 0, NEAR: 1, WITHIN: 2}


def credit_limits_enabled() -> bool:
	return bool(cint(frappe.db.get_single_value("Sourcing Settings", SHOW_FIELD)))


def ensure_enabled() -> None:
	if not credit_limits_enabled():
		frappe.throw(_("Credit limits are not shown on the portal."), frappe.PermissionError)


def credit_customer(customer: str | None) -> str:
	if not customer:
		frappe.throw(_("Choose the customer account to see credit for."))

	party_scope(CUSTOMER, customer)
	if branch_restrictions().get(customer) is not None:
		frappe.throw(
			_("Only people who can see every branch of this account can see its credit."),
			frappe.PermissionError,
		)

	return customer


def credit_companies(customer: str) -> list[str]:
	with_limits = frappe.get_all(
		CREDIT_LIMIT,
		filters={"parenttype": CUSTOMER, "parent": customer, "credit_limit": (">", 0)},
		pluck="company",
	)
	return sorted(set(order_companies(customer)) | set(with_limits))


def invoiced_balances(customer: str, companies: list[str]) -> dict[str, float]:
	gl = frappe.qb.DocType("GL Entry")
	rows = (
		frappe.qb.from_(gl)
		.select(gl.company, (Sum(gl.debit) - Sum(gl.credit)).as_("balance"))
		.where(gl.party_type == CUSTOMER)
		.where(gl.party == customer)
		.where(gl.is_cancelled == 0)
		.where(gl.company.isin(companies or [""]))
		.groupby(gl.company)
	).run(as_dict=True)
	return {row.company: flt(row.balance) for row in rows}


def credit_state(used: float, limit: float) -> str:
	if used > limit:
		return OVER
	if used >= limit * NEAR_LIMIT_PERCENT / 100:
		return NEAR
	return WITHIN


def company_credit(customer: str, company: str, invoiced: float) -> dict | None:
	limit = flt(get_credit_limit(customer, company))
	if limit <= 0:
		return None

	currency = frappe.get_cached_value("Company", company, "default_currency")
	precision = frappe.get_precision(CREDIT_LIMIT, "credit_limit", currency) or 2
	used = flt(get_customer_outstanding(customer, company), precision)
	invoiced = flt(invoiced, precision)

	return {
		"company": company,
		"currency": currency,
		"credit_limit": limit,
		"used": used,
		"unpaid_invoices": invoiced,
		"not_yet_invoiced": flt(max(used - invoiced, 0), precision),
		"available": flt(max(limit - used, 0), precision),
		"over_by": flt(max(used - limit, 0), precision),
		"used_percent": flt(used / limit * 100, 1),
		"state": credit_state(used, limit),
	}


@frappe.whitelist()
def get_credit_status(customer: str) -> ApiResponse[dict]:
	ensure_enabled()
	customer = credit_customer(customer)

	companies = credit_companies(customer)
	invoiced = invoiced_balances(customer, companies)
	rows = sorted(
		(
			row
			for row in (company_credit(customer, company, invoiced.get(company, 0)) for company in companies)
			if row
		),
		key=lambda row: (STATE_ORDER[row["state"]], row["company"]),
	)

	return ApiResponse.success(
		data={
			"rows": rows,
			"over_limit": [row["company"] for row in rows if row["state"] == OVER],
			"near_limit": [row["company"] for row in rows if row["state"] == NEAR],
		}
	)
