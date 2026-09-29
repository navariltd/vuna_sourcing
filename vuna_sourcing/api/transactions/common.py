# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from collections import Counter
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, getdate, nowdate
from frappe.utils.html_utils import sanitize_html

from vuna_sourcing.api.portal import check_party_access, get_linked_parties


def my_parties(party_type: str, user: str | None = None) -> list[str]:
	return [party["name"] for party in get_linked_parties(user) if party["party_type"] == party_type]


def party_scope(party_type: str, party: str | None = None) -> list[str]:
	if not party:
		return my_parties(party_type)

	check_party_access(party_type, party)
	return [party]


def empty_page(start: int, limit: int) -> dict:
	return {"rows": [], "total": 0, "start": cint(start), "limit": cint(limit), "counts": {}}


def page_of(rows: list[dict], start: int, limit: int, counts: dict | None = None) -> dict:
	start = max(cint(start), 0)
	limit = max(cint(limit), 1)

	if counts is None:
		counts = dict(Counter(row["status"] for row in rows if row.get("status")))

	return {
		"rows": rows[start : start + limit],
		"total": len(rows),
		"start": start,
		"limit": limit,
		"counts": counts,
	}


def owned_document(doctype: str, name: str, filters: dict):
	mine = frappe.db.get_value(doctype, {**filters, "name": name}, "name")
	if not mine:
		frappe.throw(_("This document does not belong to you."), frappe.PermissionError)

	return frappe.get_doc(doctype, mine)


def find_documents(
	doctype: str,
	filters: dict,
	search: str | None,
	fields: list[str],
	search_fields: tuple[str, ...] = ("name",),
	order_by: str = "creation desc",
) -> list:
	or_filters = None
	if search and search.strip():
		pattern = f"%{search.strip()}%"
		or_filters = [[field, "like", pattern] for field in search_fields]

	return frappe.get_all(doctype, filters=filters, or_filters=or_filters, fields=fields, order_by=order_by)


def submitted_parents(child_doctype: str, link_field: str, name: str) -> list[str]:
	return list(
		dict.fromkeys(
			frappe.get_all(
				child_doctype,
				filters={link_field: name, "docstatus": 1},
				pluck="parent",
				order_by="creation desc",
			)
		)
	)


def returns_against(doctype: str, name: str) -> list[dict]:
	return frappe.get_all(
		doctype,
		filters={"return_against": name, "is_return": 1, "docstatus": 1},
		fields=["name", "posting_date", "grand_total", "status"],
		order_by="posting_date desc",
	)


def distinct(rows: list[dict], key: str) -> list[str]:
	return sorted({row[key] for row in rows if row.get(key)})


def payments_against(doctype: str, name: str) -> list[dict]:
	references = frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_doctype": doctype, "reference_name": name, "docstatus": 1},
		fields=["parent", "allocated_amount"],
	)
	if not references:
		return []

	allocated = {row.parent: row.allocated_amount for row in references}
	entries = frappe.get_all(
		"Payment Entry",
		filters={"name": ("in", list(allocated)), "docstatus": 1},
		fields=["name", "posting_date", "mode_of_payment", "reference_no", "paid_amount"],
		order_by="posting_date desc",
	)

	return [
		{
			"name": entry.name,
			"posting_date": entry.posting_date,
			"mode_of_payment": entry.mode_of_payment,
			"reference_no": entry.reference_no,
			"allocated_amount": allocated.get(entry.name),
		}
		for entry in entries
	]


def safe_html(value: str | None) -> str | None:
	if not value:
		return value

	return sanitize_html(value, always_sanitize=True)


def item_description(item) -> dict:
	if item.item_name and item.description:
		return {"item_name": item.item_name, "description": item.description}

	stored = frappe.db.get_value("Item", item.item_code, ["item_name", "description"], as_dict=True) or {}
	return {
		"item_name": item.item_name or stored.get("item_name") or item.item_code,
		"description": item.description or stored.get("description"),
	}


def line_item(item, **extra) -> dict:
	return {
		"name": item.name,
		"item_code": item.item_code,
		**item_description(item),
		"qty": item.qty,
		"uom": item.uom,
		"rate": item.rate,
		"amount": item.amount,
		**extra,
	}


STATEMENT_FIELDS = (
	"voucher_type",
	"voucher_no",
	"posting_date",
	"due_date",
	"bill_no",
	"po_no",
	"invoiced",
	"paid",
	"credit_note",
	"outstanding",
	"age",
	"currency",
)


@contextmanager
def as_administrator():
	session = frappe.local.session
	user = session.user
	session.user = "Administrator"
	frappe.local.user_perms = None
	try:
		yield
	finally:
		session.user = user
		frappe.local.user_perms = None


def statement_companies(party_type: str, parties: list[str]) -> list[str]:
	return frappe.get_all(
		"Payment Ledger Entry",
		filters={"party_type": party_type, "party": ("in", parties or [""]), "delinked": 0},
		pluck="company",
		distinct=True,
		order_by="company asc",
	)


def outstanding_statement(account_type: str, party_type: str, parties: list[str]) -> dict:
	from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport

	naming_by = (
		["Selling Settings", "cust_master_name"]
		if account_type == "Receivable"
		else ["Buying Settings", "supp_master_name"]
	)
	report_date = nowdate()
	companies = []

	for company in statement_companies(party_type, parties):
		report = ReceivablePayableReport(
			{
				"company": company,
				"report_date": report_date,
				"ageing_based_on": "Due Date",
				"party_type": party_type,
				"party": parties,
				"in_party_currency": 1,
			}
		)
		with as_administrator():
			_columns, data, *_rest = report.run({"account_type": account_type, "naming_by": naming_by})

		rows = [row for row in data if isinstance(row, dict) and row.get("voucher_no")]

		companies.append(
			{
				"company": company,
				"currency": next((row.get("currency") for row in rows if row.get("currency")), None)
				or frappe.get_cached_value("Company", company, "default_currency"),
				"rows": [{field: row.get(field) for field in STATEMENT_FIELDS} for row in rows],
				"totals": {
					field: flt(sum(flt(row.get(field)) for row in rows), 2)
					for field in ("invoiced", "paid", "credit_note", "outstanding")
				},
			}
		)

	return {"report_date": report_date, "companies": companies}


def month_starts(count: int = 12) -> list:
	first = getdate(nowdate()).replace(day=1)
	return [add_months(first, offset) for offset in range(-(count - 1), 1)]


def monthly_totals(doctype: str, filters: dict, date_field: str, value_field: str) -> list[dict]:
	months = month_starts()
	totals = dict.fromkeys(months, 0.0)

	for row in frappe.get_all(
		doctype,
		filters={**filters, date_field: (">=", months[0])},
		fields=[date_field, value_field],
	):
		month = getdate(row[date_field]).replace(day=1)
		if month in totals:
			totals[month] += flt(row[value_field])

	return [{"month": month.isoformat(), "value": flt(total, 2)} for month, total in totals.items()]


def status_counts(doctype: str, filters: dict) -> list[dict]:
	counts = Counter(frappe.get_all(doctype, filters=filters, pluck="status"))
	return [{"status": status, "count": count} for status, count in counts.most_common() if status]


def balance(statement: dict) -> dict:
	section = next(iter(statement["companies"]), None)
	return {
		"outstanding": section["totals"]["outstanding"] if section else 0,
		"overdue": flt(
			sum(
				flt(row["outstanding"])
				for row in (section["rows"] if section else [])
				if flt(row["outstanding"]) > 0
				and row.get("due_date")
				and getdate(row["due_date"]) < getdate(nowdate())
			),
			2,
		),
		"currency": section["currency"] if section else None,
	}


def company_currency() -> str | None:
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	return frappe.get_cached_value("Company", company, "default_currency") if company else None
