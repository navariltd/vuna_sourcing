# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cstr

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.branches import customer_scope_filters
from vuna_sourcing.api.transactions.common import all_of, party_scope
from vuna_sourcing.api.transactions.credit_requests import DOCTYPE as CREDIT_REQUEST
from vuna_sourcing.api.transactions.credit_requests import credit_requests_enabled
from vuna_sourcing.api.transactions.customer import (
	DELIVERY_NOTE,
	QUOTATION,
	SALES_INVOICE,
	SALES_ORDER,
	customer_filters,
	order_filters,
)
from vuna_sourcing.api.transactions.customer_orders import FROM_PORTAL_FIELD
from vuna_sourcing.api.transactions.supplier import (
	PURCHASE_INVOICE,
	PURCHASE_ORDER,
	RFQ,
	RFQ_SUPPLIER,
	SUPPLIER_QUOTATION,
	supplier_filters,
)
from vuna_sourcing.utils import CUSTOMER, PARTY_TYPES

MIN_QUERY = 2
MAX_QUERY = 140
PER_GROUP = 5


def matching(
	doctype: str,
	filters: list | dict,
	query: str,
	search_fields: tuple[str, ...],
	fields: list[str],
	date_field: str,
) -> list[dict]:
	pattern = f"%{query}%"
	return frappe.get_all(
		doctype,
		filters=filters,
		or_filters=[[field, "like", pattern] for field in search_fields],
		fields=["name", *fields],
		order_by=f"{date_field} desc, creation desc",
		limit=PER_GROUP,
	)


def result(row: dict, date_field: str, detail: str | None = None) -> dict:
	return {
		"name": row.name,
		"date": row.get(date_field),
		"detail": detail,
		"status": row.get("status"),
		"amount": row.get("grand_total"),
		"currency": row.get("currency"),
	}


def group(doctype: str, rows: list[dict], date_field: str, detail_field: str | None = None) -> dict:
	return {
		"doctype": doctype,
		"results": [result(row, date_field, row.get(detail_field) if detail_field else None) for row in rows],
	}


def customer_groups(customers: list[str], query: str) -> list[dict]:
	money = ["grand_total", "currency", "status"]
	order = frappe.qb.DocType(SALES_ORDER)
	visible_orders = all_of(
		order_filters(customers), [(order.docstatus == 1) | (order[FROM_PORTAL_FIELD] == 1)]
	)

	groups = [
		group(
			QUOTATION,
			matching(
				QUOTATION,
				customer_filters(QUOTATION, customers),
				query,
				("name",),
				[*money, "transaction_date"],
				"transaction_date",
			),
			"transaction_date",
		),
		group(
			SALES_ORDER,
			matching(
				SALES_ORDER,
				visible_orders,
				query,
				("name", "po_no"),
				[*money, "transaction_date", "po_no"],
				"transaction_date",
			),
			"transaction_date",
			"po_no",
		),
		group(
			DELIVERY_NOTE,
			matching(
				DELIVERY_NOTE,
				customer_filters(DELIVERY_NOTE, customers),
				query,
				("name", "po_no"),
				[*money, "posting_date", "po_no"],
				"posting_date",
			),
			"posting_date",
			"po_no",
		),
		group(
			SALES_INVOICE,
			matching(
				SALES_INVOICE,
				customer_filters(SALES_INVOICE, customers),
				query,
				("name", "po_no"),
				[*money, "posting_date", "po_no"],
				"posting_date",
			),
			"posting_date",
			"po_no",
		),
	]

	if credit_requests_enabled():
		groups.append(
			group(
				CREDIT_REQUEST,
				matching(
					CREDIT_REQUEST,
					all_of(customer_scope_filters(CREDIT_REQUEST, customers), {"docstatus": ("!=", 0)}),
					query,
					("name", "sales_invoice"),
					["transaction_date", "sales_invoice", "request_status as status", "currency"],
					"transaction_date",
				),
				"transaction_date",
				"sales_invoice",
			)
		)

	return groups


def supplier_groups(suppliers: list[str], query: str) -> list[dict]:
	money = ["grand_total", "currency", "status"]
	invited = frappe.get_all(
		RFQ_SUPPLIER,
		filters={"parenttype": RFQ, "supplier": ("in", suppliers), "parent": ("like", f"%{query}%")},
		pluck="parent",
		distinct=True,
	)

	return [
		group(
			RFQ,
			matching(
				RFQ,
				{"name": ("in", invited or [""]), "docstatus": 1},
				query,
				("name",),
				["transaction_date", "status"],
				"transaction_date",
			),
			"transaction_date",
		),
		group(
			SUPPLIER_QUOTATION,
			matching(
				SUPPLIER_QUOTATION,
				supplier_filters(suppliers),
				query,
				("name",),
				[*money, "transaction_date"],
				"transaction_date",
			),
			"transaction_date",
		),
		group(
			PURCHASE_ORDER,
			matching(
				PURCHASE_ORDER,
				supplier_filters(suppliers),
				query,
				("name",),
				[*money, "transaction_date"],
				"transaction_date",
			),
			"transaction_date",
		),
		group(
			PURCHASE_INVOICE,
			matching(
				PURCHASE_INVOICE,
				supplier_filters(suppliers),
				query,
				("name", "bill_no"),
				[*money, "posting_date", "bill_no"],
				"posting_date",
			),
			"posting_date",
			"bill_no",
		),
	]


@frappe.whitelist()
def search_documents(party_type: str, party: str, query: str | None = None) -> ApiResponse[dict]:
	if party_type not in PARTY_TYPES:
		frappe.throw(_("Choose a supplier or customer account to search."))

	parties = party_scope(party_type, party)
	query = cstr(query).strip()[:MAX_QUERY]
	if len(query) < MIN_QUERY or not parties:
		return ApiResponse.success(data={"query": query, "groups": []})

	groups = customer_groups(parties, query) if party_type == CUSTOMER else supplier_groups(parties, query)
	return ApiResponse.success(
		data={"query": query, "groups": [entry for entry in groups if entry["results"]]}
	)
