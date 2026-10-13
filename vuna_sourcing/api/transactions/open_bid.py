# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, get_fullname

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.bidding import (
	OPEN_BID,
	as_iso,
	closes_at_iso,
	closing_passed,
	is_closed,
	is_open_bid,
)
from vuna_sourcing.api.transactions.supplier import (
	NO_QUOTE,
	RECEIVED,
	RFQ,
	RFQ_SUPPLIER,
	SUPPLIER_QUOTATION,
	invited_supplier,
	is_sent,
	supplier_scope,
)
from vuna_sourcing.vuna_sourcing.doctype.rfq_bid_log.rfq_bid_log import BID_LOG

BID_LOG_ITEM = "RFQ Bid Log Item"


def running_open_bid_of(quote) -> str | None:
	requests = list({row.request_for_quotation for row in quote.get("items") if row.request_for_quotation})
	if not requests:
		return None

	running = frappe.get_all(
		RFQ,
		filters={"name": ("in", requests), "bidding_method": OPEN_BID},
		fields=["name", "bid_closing", "schedule_date"],
	)
	return next((request.name for request in running if not closing_passed(request)), None)


def bidder_alias(position: int) -> str:
	letters = ""
	position += 1
	while position:
		position, rest = divmod(position - 1, 26)
		letters = chr(65 + rest) + letters
	return _("Bidder {0}").format(letters)


def bid_log(filters: dict) -> list:
	return frappe.get_all(
		BID_LOG,
		filters=filters,
		fields=[
			"name",
			"supplier",
			"revision",
			"placed_at",
			"placed_by",
			"currency",
			"total",
			"base_total",
			"valid_till",
		],
		order_by="placed_at asc, revision asc",
	)


def lines_of(bids: list) -> dict[str, list]:
	lines = defaultdict(list)
	for line in frappe.get_all(
		BID_LOG_ITEM,
		filters={"parent": ("in", [bid.name for bid in bids] or [""]), "parenttype": BID_LOG},
		fields=[
			"parent",
			"request_for_quotation_item",
			"item_code",
			"qty",
			"rate",
			"base_rate",
			"amount",
			"lead_time_days",
		],
		order_by="idx asc",
	):
		lines[line.parent].append(line)
	return lines


def bid_board(request, supplier: str) -> dict:
	bids = bid_log({"request_for_quotation": request.name})
	aliases = {}
	revisions = defaultdict(int)
	current = {}
	for bid in bids:
		aliases.setdefault(bid.supplier, bidder_alias(len(aliases)))
		revisions[bid.supplier] += 1
		current[bid.supplier] = bid

	live = sorted(current.values(), key=lambda bid: (bid.base_total, bid.placed_at))
	lines = lines_of(live)

	rows = [
		{
			"alias": aliases[bid.supplier],
			"rank": rank,
			"total": bid.base_total,
			"rates": {line.request_for_quotation_item: line.base_rate for line in lines[bid.name]},
			"bid_at": as_iso(bid.placed_at),
			"revisions": revisions[bid.supplier],
			"is_you": bid.supplier == supplier,
		}
		for rank, bid in enumerate(live, start=1)
	]

	lowest_rates = {}
	for row in rows:
		for item, rate in row["rates"].items():
			if rate and (item not in lowest_rates or rate < lowest_rates[item]):
				lowest_rates[item] = rate

	return {
		"currency": frappe.get_cached_value("Company", request.company, "default_currency"),
		"closes_at": closes_at_iso(request),
		"closed": is_closed(request),
		"bidders": len(rows),
		"lowest": rows[0]["total"] if rows else None,
		"lowest_rates": lowest_rates,
		"bids": rows,
		"your_bids": [
			{
				"name": bid.name,
				"total": bid.base_total,
				"bid_at": as_iso(bid.placed_at),
				"live": bid is current.get(supplier),
			}
			for bid in reversed(bids)
			if bid.supplier == supplier
		],
	}


@frappe.whitelist()
def get_open_bids(name: str, supplier: str | None = None) -> ApiResponse[dict]:
	supplier = invited_supplier(name, supplier)
	request = frappe.get_doc(RFQ, name)

	if request.docstatus != 1 or not is_open_bid(request):
		frappe.throw(_("{0} is not an open bid.").format(name), frappe.PermissionError)

	if not is_sent(name, supplier):
		frappe.throw(_("Place your bid to see the other bids."), frappe.PermissionError)

	return ApiResponse.success(data=bid_board(request, supplier))


def live_bid_summary(request, supplier: str, has_bid: bool) -> dict:
	summary = {
		"name": request.name,
		"supplier": supplier,
		"company": request.company,
		"closes_at": closes_at_iso(request),
		"has_bid": has_bid,
		"status": "Bidding" if has_bid else "Invited",
		"rank": None,
		"bidders": None,
		"lowest": None,
		"your_total": None,
		"currency": None,
	}
	if not has_bid:
		return summary

	board = bid_board(request, supplier)
	yours = next((row for row in board["bids"] if row["is_you"]), None)
	summary.update(
		rank=yours["rank"] if yours else None,
		bidders=board["bidders"],
		lowest=board["lowest"],
		your_total=yours["total"] if yours else None,
		currency=board["currency"],
	)
	return summary


@frappe.whitelist()
def get_live_bids(supplier: str | None = None) -> ApiResponse[list[dict]]:
	suppliers = supplier_scope(supplier)
	if not suppliers:
		return ApiResponse.success(data=[])

	invitations = {
		row.parent: row
		for row in frappe.get_all(
			RFQ_SUPPLIER,
			filters={"parenttype": RFQ, "supplier": ("in", suppliers)},
			fields=["parent", "supplier", "quote_status"],
		)
		if row.quote_status != NO_QUOTE
	}
	if not invitations:
		return ApiResponse.success(data=[])

	requests = frappe.get_all(
		RFQ,
		filters={"name": ("in", list(invitations)), "docstatus": 1, "bidding_method": OPEN_BID},
		fields=["name", "company", "bid_closing", "schedule_date", "quotes_opened"],
	)

	live = [
		live_bid_summary(
			request,
			invitations[request.name].supplier,
			invitations[request.name].quote_status == RECEIVED,
		)
		for request in requests
		if not is_closed(request)
	]
	live.sort(key=lambda bid: bid["closes_at"] or "9999")
	return ApiResponse.success(data=live)


@frappe.whitelist()
def get_bid_history(supplier_quotation: str) -> ApiResponse[dict]:
	quote = frappe.get_doc(SUPPLIER_QUOTATION, supplier_quotation)
	quote.check_permission("read")

	bids = bid_log({"supplier_quotation": quote.name})
	lines = lines_of(bids)

	history = []
	previous = None
	for bid in bids:
		history.append(
			{
				"name": bid.name,
				"revision": bid.revision,
				"placed_at": bid.placed_at,
				"placed_by": get_fullname(bid.placed_by),
				"currency": bid.currency,
				"total": bid.total,
				"valid_till": bid.valid_till,
				"change": flt(bid.total - previous.total) if previous else None,
				"items": lines[bid.name],
			}
		)
		previous = bid

	return ApiResponse.success(
		data={
			"supplier_quotation": quote.name,
			"supplier": quote.supplier_name or quote.supplier,
			"request_for_quotation": frappe.db.get_value(
				BID_LOG, {"supplier_quotation": quote.name}, "request_for_quotation"
			),
			"bids": list(reversed(history)),
		}
	)
