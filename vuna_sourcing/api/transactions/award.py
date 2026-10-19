# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt, fmt_money, format_datetime, getdate, now_datetime, today

from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.bidding import (
	AWARD,
	AWARD_ITEM,
	AWARDED,
	NOT_AWARDED,
	OUTCOME_AWARDED,
	OUTCOME_NOT_SELECTED,
	PARTIALLY_AWARDED,
	PENDING_SELECTION,
	SEALED_BID,
	closes_at,
	closing_passed,
)
from vuna_sourcing.api.transactions.supplier import (
	PURCHASE_ORDER,
	RECEIVED,
	RFQ,
	RFQ_ITEM,
	RFQ_SUPPLIER,
	SUPPLIER_QUOTATION,
	SUPPLIER_QUOTATION_ITEM,
)

OPEN_STATUSES = (PENDING_SELECTION, PARTIALLY_AWARDED)
FINAL_STATUSES = (AWARDED, NOT_AWARDED)


def quoted_lines(request: str) -> list[dict]:
	quotation = frappe.qb.DocType(SUPPLIER_QUOTATION)
	item = frappe.qb.DocType(SUPPLIER_QUOTATION_ITEM)
	return (
		frappe.qb.from_(item)
		.join(quotation)
		.on(quotation.name == item.parent)
		.select(
			quotation.name.as_("supplier_quotation"),
			quotation.supplier,
			quotation.supplier_name,
			quotation.currency,
			quotation.creation,
			quotation.valid_till,
			item.name.as_("supplier_quotation_item"),
			item.request_for_quotation_item,
			item.qty,
			item.rate,
			item.amount,
			item.base_rate,
			item.base_amount,
		)
		.where(item.request_for_quotation == request)
		.where(quotation.docstatus == 1)
		.orderby(quotation.creation)
		.orderby(item.idx)
	).run(as_dict=True)


def bids_by_line(request: str) -> dict[str, list]:
	bids = defaultdict(list)
	for bid in quoted_lines(request):
		line = bids[bid.request_for_quotation_item]
		if not any(other.supplier_quotation == bid.supplier_quotation for other in line):
			line.append(bid)

	for line in bids.values():
		line.sort(key=lambda bid: (flt(bid.base_rate), bid.creation))
		lowest = flt(line[0].base_rate)
		for rank, bid in enumerate(line, start=1):
			bid.item_rank = rank
			bid.is_lowest = flt(bid.base_rate) == lowest
	return bids


def rfq_lines(request: str) -> list[dict]:
	return frappe.get_all(
		RFQ_ITEM,
		filters={"parent": request, "parenttype": RFQ},
		fields=["name", "item_code", "item_name", "qty", "uom", "award_status"],
		order_by="idx asc",
	)


def awarded_lines(request: str, exclude: str | None = None) -> dict[str, dict]:
	filters = {"request_for_quotation": request, "docstatus": 1}
	if exclude:
		filters["name"] = ("!=", exclude)
	awards = frappe.get_all(AWARD, filters=filters, pluck="name")
	if not awards:
		return {}

	return {
		row.request_for_quotation_item: row
		for row in frappe.get_all(
			AWARD_ITEM,
			filters={"parenttype": AWARD, "parent": ("in", awards)},
			fields=[
				"parent",
				"request_for_quotation_item",
				"supplier",
				"supplier_quotation",
				"supplier_quotation_item",
			],
		)
	}


def open_lines(request: str, award: str | None = None) -> list[dict]:
	decided = awarded_lines(request, exclude=award)
	return [
		line for line in rfq_lines(request) if line.name not in decided and line.award_status != NOT_AWARDED
	]


def ranked_quotes(request: str, lines: list[str]) -> list[dict]:
	wanted = set(lines)
	quotes = {}
	for bid in quoted_lines(request):
		if bid.request_for_quotation_item not in wanted:
			continue
		quote = quotes.setdefault(
			bid.supplier_quotation,
			frappe._dict(
				supplier_quotation=bid.supplier_quotation,
				supplier=bid.supplier,
				supplier_name=bid.supplier_name,
				currency=bid.currency,
				creation=bid.creation,
				valid_till=bid.valid_till,
				total=0,
				base_total=0,
				lines=set(),
			),
		)
		if bid.request_for_quotation_item in quote.lines:
			continue
		quote.lines.add(bid.request_for_quotation_item)
		quote.total += flt(bid.amount)
		quote.base_total += flt(bid.base_amount)

	complete = [quote for quote in quotes.values() if wanted and quote.lines == wanted]
	complete.sort(key=lambda quote: (flt(quote.base_total), quote.creation))
	lowest = flt(complete[0].base_total) if complete else None
	for rank, quote in enumerate(complete, start=1):
		quote.rank = rank
		quote.is_lowest = flt(quote.base_total) == lowest
		del quote.lines
	return complete


def supplier_hold(supplier: str, on: str) -> str | None:
	details = frappe.db.get_value(
		"Supplier", supplier, ["disabled", "on_hold", "hold_type", "release_date"], as_dict=True
	)
	if not details:
		return None
	if cint(details.disabled):
		return _("{0} is disabled.").format(frappe.bold(supplier))
	if (
		cint(details.on_hold)
		and details.hold_type == "All"
		and (not details.release_date or getdate(details.release_date) > getdate(on))
	):
		return _("{0} is on hold and cannot receive orders.").format(frappe.bold(supplier))
	return None


def quotation_problems(supplier_quotations: set[str], on) -> list[str]:
	problems = []
	for name in sorted(supplier_quotations):
		valid_till, supplier = frappe.db.get_value(SUPPLIER_QUOTATION, name, ["valid_till", "supplier"])
		if valid_till and getdate(valid_till) < getdate(on):
			problems.append(
				_("{0} expired on {1}.").format(frappe.bold(name), frappe.format(valid_till, "Date"))
			)
		if hold := supplier_hold(supplier, on):
			problems.append(hold)
	return problems


def award_blockers(request) -> list[str]:
	blockers = []
	if request.docstatus != 1:
		blockers.append(_("Submit {0} before awarding it.").format(request.name))

	if not closing_passed(request):
		closing = closes_at(request)
		blockers.append(
			_("Bids close at {0}.").format(format_datetime(closing))
			if closing
			else _("Set when bids close before awarding.")
		)

	if request.get("bidding_method") == SEALED_BID and not cint(request.get("quotes_opened")):
		blockers.append(_("The opening committee has not opened the quotations yet."))

	if not quoted_lines(request.name):
		blockers.append(_("No supplier quotation for this request has been submitted yet."))

	return blockers


def refresh_award_status(name: str) -> str | None:
	request = frappe.get_doc(RFQ, name)
	awarded = awarded_lines(name)

	for row in request.items:
		status = (
			AWARDED if row.name in awarded else (NOT_AWARDED if row.award_status == NOT_AWARDED else None)
		)
		if (row.award_status or None) != status:
			frappe.db.set_value(RFQ_ITEM, row.name, "award_status", status, update_modified=False)
			row.award_status = status

	decided = [row for row in request.items if row.award_status]
	if request.items and len(decided) == len(request.items):
		status = AWARDED if awarded else NOT_AWARDED
	elif awarded:
		status = PARTIALLY_AWARDED
	elif request.docstatus == 1 and not award_blockers(request):
		status = PENDING_SELECTION
	else:
		status = None

	request.db_set("award_status", status, update_modified=False)
	set_outcomes(request, awarded, final=status in FINAL_STATUSES)
	return status


def set_outcomes(request, awarded: dict[str, dict], final: bool) -> None:
	winners = {row.supplier for row in awarded.values()}
	winning_quotes = {row.supplier_quotation for row in awarded.values()}
	quotes = {bid.supplier_quotation: bid.supplier for bid in quoted_lines(request.name)}
	quoted = set(quotes.values()) | {
		row.supplier for row in request.suppliers if row.quote_status == RECEIVED
	}

	def outcome(won: bool) -> str | None:
		if won:
			return OUTCOME_AWARDED
		return OUTCOME_NOT_SELECTED if final else None

	for row in request.suppliers:
		value = outcome(row.supplier in winners) if row.supplier in quoted else None
		frappe.db.set_value(RFQ_SUPPLIER, row.name, "award_outcome", value, update_modified=False)

	for quote in quotes:
		frappe.db.set_value(
			SUPPLIER_QUOTATION,
			quote,
			"award_outcome",
			outcome(quote in winning_quotes),
			update_modified=False,
		)


def outcomes(request: str) -> dict[str, str | None]:
	return dict(
		frappe.get_all(
			RFQ_SUPPLIER,
			filters={"parent": request, "parenttype": RFQ},
			fields=["supplier", "award_outcome"],
			as_list=True,
		)
	)


def requests_of(quote) -> list[str]:
	return list({row.request_for_quotation for row in quote.get("items") if row.request_for_quotation})


def refresh_for_quotation(doc, method: str | None = None) -> None:
	for request in requests_of(doc):
		refresh_award_status(request)


def refresh_pending_selection() -> None:
	for name in frappe.get_all(
		RFQ,
		filters={"docstatus": 1, "award_status": ("is", "not set"), "bid_closing": ("<=", now_datetime())},
		pluck="name",
	):
		refresh_award_status(name)


def recipients_of(request: str, supplier: str) -> list[str]:
	listed = frappe.db.get_value(RFQ_SUPPLIER, {"parent": request, "supplier": supplier}, "email_id")
	users = frappe.get_all(
		"Portal User", filters={"parenttype": "Supplier", "parent": supplier}, pluck="user"
	)
	emails = frappe.get_all("User", filters={"name": ("in", users or [""]), "enabled": 1}, pluck="email")
	return sorted({email for email in [listed, *emails] if email})


def notify_supplier(request: str, supplier: str, subject: str, message: str) -> None:
	recipients = recipients_of(request, supplier)
	if not recipients:
		return

	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype=RFQ,
			reference_name=request,
		)
	except Exception:
		frappe.log_error("Request for Quotation award notification failed")


def notify_award(award) -> None:
	won = defaultdict(list)
	for row in award.items:
		won[row.supplier].append(row)

	for supplier, rows in won.items():
		items = "".join(
			f"<li>{escape_html(row.item_name or row.item_code)}: {flt(row.qty):g} {escape_html(row.uom or '')}</li>"
			for row in rows
		)
		notify_supplier(
			award.request_for_quotation,
			supplier,
			_("Awarded: {0}").format(award.request_for_quotation),
			_("Your quotation for {0} has been selected for these items:").format(award.request_for_quotation)
			+ f"<ul>{items}</ul>"
			+ _("Our team will be in touch with the purchase order."),
		)


def notify_not_selected(request: str, before: dict[str, str | None]) -> None:
	for supplier, outcome in outcomes(request).items():
		if outcome == OUTCOME_NOT_SELECTED and before.get(supplier) != OUTCOME_NOT_SELECTED:
			notify_supplier(
				request,
				supplier,
				_("Outcome of {0}").format(request),
				_("Thank you for your quotation for {0}. On this occasion it was not selected.").format(
					request
				),
			)


def notify_withdrawn(request: str, before: dict[str, str | None]) -> None:
	after = outcomes(request)
	for supplier, outcome in before.items():
		if outcome and after.get(supplier) != outcome:
			notify_supplier(
				request,
				supplier,
				_("Award withdrawn: {0}").format(request),
				_(
					"The award for {0} has been withdrawn while we review it. We will let you know the outcome."
				).format(request),
			)


def orders_against(supplier_quotation_items: list[str], docstatus: int) -> list[str]:
	if not supplier_quotation_items:
		return []
	return frappe.get_all(
		"Purchase Order Item",
		filters={
			"parenttype": PURCHASE_ORDER,
			"supplier_quotation_item": ("in", supplier_quotation_items),
			"docstatus": docstatus,
		},
		pluck="parent",
		distinct=True,
	)


def creates_orders_on_award() -> bool:
	return bool(cint(frappe.db.get_single_value("Sourcing Settings", "create_purchase_orders_on_award")))


def make_award_orders(award) -> list[str]:
	lines = defaultdict(list)
	for row in award.items:
		lines[row.supplier_quotation].append(row.supplier_quotation_item)

	orders = []
	for supplier_quotation, items in lines.items():
		order = make_purchase_order(supplier_quotation, args={"filtered_children": items})
		order.flags.ignore_permissions = True
		order.insert()
		orders.append(order.name)
	return orders


def awarded_quotation_items(supplier_quotation: str) -> set[str]:
	award = frappe.qb.DocType(AWARD)
	item = frappe.qb.DocType(AWARD_ITEM)
	return {
		row[0]
		for row in (
			frappe.qb.from_(item)
			.join(award)
			.on(award.name == item.parent)
			.select(item.supplier_quotation_item)
			.where(item.supplier_quotation == supplier_quotation)
			.where(award.docstatus == 1)
		).run()
	}


def sourced_quotation_items(supplier_quotation: str) -> dict[str, dict]:
	return {
		row.name: row
		for row in frappe.get_all(
			SUPPLIER_QUOTATION_ITEM,
			filters={"parent": supplier_quotation, "request_for_quotation": ("is", "set")},
			fields=["name", "request_for_quotation", "request_for_quotation_item"],
		)
	}


def required_by(order) -> None:
	references = [row.supplier_quotation_item for row in order.items if row.supplier_quotation_item]
	if not references:
		return

	rfq_lines_of = {
		row.name: row
		for row in frappe.get_all(
			SUPPLIER_QUOTATION_ITEM,
			filters={"name": ("in", references)},
			fields=["name", "request_for_quotation", "request_for_quotation_item"],
		)
	}
	line_dates = dict(
		frappe.get_all(
			RFQ_ITEM,
			filters={
				"name": ("in", [row.request_for_quotation_item for row in rfq_lines_of.values()] or [""])
			},
			fields=["name", "schedule_date"],
			as_list=True,
		)
	)
	earliest = getdate(today())

	for row in order.items:
		source = rfq_lines_of.get(row.supplier_quotation_item)
		if not source or (row.schedule_date and getdate(row.schedule_date) >= earliest):
			continue
		wanted = line_dates.get(source.request_for_quotation_item) or frappe.db.get_value(
			RFQ, source.request_for_quotation, "schedule_date"
		)
		row.schedule_date = max(getdate(wanted or earliest), earliest)

	dates = [getdate(row.schedule_date) for row in order.items if row.schedule_date]
	if dates and (not order.schedule_date or getdate(order.schedule_date) < earliest):
		order.schedule_date = min(dates)


@frappe.whitelist()
def make_purchase_order(source_name: str, target_doc=None, args=None):
	from erpnext.buying.doctype.supplier_quotation.supplier_quotation import (
		make_purchase_order as make_standard_purchase_order,
	)

	args = frappe.parse_json(args) if isinstance(args, str) else (args or frappe.flags.args or {})
	sourced = sourced_quotation_items(source_name)

	if sourced:
		awarded = awarded_quotation_items(source_name)
		if not awarded:
			frappe.throw(
				_(
					"{0} has not been awarded. Award its Request for Quotation, then order from the awarded quotation."
				).format(frappe.bold(source_name)),
				title=_("Quotation not awarded"),
			)

		every = frappe.get_all(SUPPLIER_QUOTATION_ITEM, filters={"parent": source_name}, pluck="name")
		allowed = (set(every) - set(sourced)) | awarded
		chosen = args.get("filtered_children") or every
		args["filtered_children"] = [name for name in chosen if name in allowed]

	order = make_standard_purchase_order(source_name, target_doc, args)
	required_by(order)
	return order


def validate_awarded_items(doc, method: str | None = None) -> None:
	references = {row.supplier_quotation_item for row in doc.items if row.supplier_quotation_item}
	if not references:
		return

	sourced = {
		row.name: row.parent
		for row in frappe.get_all(
			SUPPLIER_QUOTATION_ITEM,
			filters={"name": ("in", list(references)), "request_for_quotation": ("is", "set")},
			fields=["name", "parent"],
		)
	}
	awarded = set()
	for quotation in set(sourced.values()):
		awarded |= awarded_quotation_items(quotation)

	for row in doc.items:
		if row.supplier_quotation_item in sourced and row.supplier_quotation_item not in awarded:
			frappe.throw(
				_(
					"Row #{0}: {1} from {2} was not awarded to this supplier. Remove it, or order it from the awarded quotation."
				).format(row.idx, frappe.bold(row.item_code), sourced[row.supplier_quotation_item]),
				title=_("Item not awarded"),
			)


BID_FIELDS = (
	"supplier_quotation",
	"supplier",
	"supplier_name",
	"currency",
	"supplier_quotation_item",
	"rate",
	"amount",
	"base_rate",
	"base_amount",
	"item_rank",
	"is_lowest",
	"valid_till",
)
QUOTE_FIELDS = (
	"supplier_quotation",
	"supplier",
	"supplier_name",
	"currency",
	"total",
	"base_total",
	"rank",
	"is_lowest",
	"valid_till",
)


TOP_BIDS = 3


def top_bids(bids: list) -> list:
	return bids if len(bids) <= TOP_BIDS + 1 else bids[:TOP_BIDS]


def as_bid(bid) -> dict:
	return {field: bid.get(field) for field in BID_FIELDS}


def award_overview(request, award: str | None = None) -> dict:
	lines = open_lines(request.name, award)
	bids = bids_by_line(request.name)
	return {
		"award_status": request.get("award_status"),
		"blockers": award_blockers(request),
		"supplier_count": len({bid.supplier for line in bids.values() for bid in line}),
		"lines": [
			{
				"request_for_quotation_item": line.name,
				"item_code": line.item_code,
				"item_name": line.item_name,
				"qty": line.qty,
				"uom": line.uom,
				"bid_count": len(bids.get(line.name, [])),
				"top_bids": [as_bid(bid) for bid in top_bids(bids.get(line.name, []))],
			}
			for line in lines
		],
		"quotes": [
			{field: quote.get(field) for field in QUOTE_FIELDS}
			for quote in ranked_quotes(request.name, [line.name for line in lines])
		],
	}


def staff_request(name: str):
	frappe.has_permission(AWARD, "read", throw=True)
	request = frappe.get_doc(RFQ, name)
	request.check_permission("read")
	return request


@frappe.whitelist()
def get_award_overview(name: str, award: str | None = None) -> ApiResponse[dict]:
	return ApiResponse.success(data=award_overview(staff_request(name), award))


@frappe.whitelist()
def get_item_bids(name: str, request_for_quotation_item: str) -> ApiResponse[list[dict]]:
	staff_request(name)
	return ApiResponse.success(
		data=[as_bid(bid) for bid in bids_by_line(name).get(request_for_quotation_item, [])]
	)


def matches(text: str, *values) -> bool:
	return not text or any(text in (value or "").lower() for value in values)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def quotation_query(doctype, txt, searchfield, start, page_len, filters):
	request = filters.get("request_for_quotation")
	if not request:
		return []
	staff_request(request)
	text = (txt or "").lower()

	if line := filters.get("request_for_quotation_item"):
		options = [
			(
				bid.supplier_quotation,
				bid.supplier_name or bid.supplier,
				_("{0} each · rank {1}").format(fmt_money(bid.rate, currency=bid.currency), bid.item_rank)
				+ (" · " + _("lowest") if bid.is_lowest else ""),
			)
			for bid in bids_by_line(request).get(line, [])
			if matches(text, bid.supplier_quotation, bid.supplier_name, bid.supplier)
		]
	else:
		lines = [row.name for row in open_lines(request, filters.get("award"))]
		options = [
			(
				quote.supplier_quotation,
				quote.supplier_name or quote.supplier,
				_("{0} total · rank {1}").format(fmt_money(quote.total, currency=quote.currency), quote.rank)
				+ (" · " + _("lowest") if quote.is_lowest else ""),
			)
			for quote in ranked_quotes(request, lines)
			if matches(text, quote.supplier_quotation, quote.supplier_name, quote.supplier)
		]

	start = cint(start)
	return options[start : start + cint(page_len)]


@frappe.whitelist(methods=["POST"])
def close_remaining_items(name: str, reason: str) -> ApiResponse[dict]:
	frappe.has_permission(AWARD, "submit", throw=True)
	request = staff_request(name)
	reason = (reason or "").strip()

	if not reason:
		frappe.throw(_("Give a reason for closing the items on {0} without an award.").format(name))

	if refresh_award_status(name) not in OPEN_STATUSES:
		frappe.throw(
			_("Only a request pending selection or partially awarded can be closed."),
			title=_("Cannot close {0}").format(name),
		)

	before = outcomes(name)
	for line in open_lines(name):
		frappe.db.set_value(RFQ_ITEM, line.name, "award_status", NOT_AWARDED, update_modified=False)

	request.db_set("award_remarks", reason, update_modified=False)
	request.add_comment("Comment", _("Closed without an award: {0}").format(reason))
	status = refresh_award_status(name)
	notify_not_selected(name, before)

	request.reload()
	message = (
		_("{0} was closed without an award.").format(name)
		if status == NOT_AWARDED
		else _("The remaining items on {0} were closed without an award.").format(name)
	)
	return ApiResponse.success(message, award_overview(request))
