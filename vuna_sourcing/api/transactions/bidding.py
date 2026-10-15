# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from datetime import datetime, time
from zoneinfo import ZoneInfo

from frappe.utils import cint, get_datetime, get_system_timezone, getdate, now_datetime

SEALED_BID = "Sealed Bid"
OPEN_BID = "Open Bid"

PENDING_SELECTION = "Pending Selection"
AWARDED = "Awarded"
NOT_AWARDED = "Not Awarded"

OUTCOME_AWARDED = "Awarded"
OUTCOME_NOT_SELECTED = "Not Selected"


def closes_at(request) -> datetime | None:
	if request.get("bid_closing"):
		return get_datetime(request.bid_closing)
	if request.get("schedule_date"):
		return datetime.combine(getdate(request.schedule_date), time.max)
	return None


def as_iso(value) -> str | None:
	if not value:
		return None
	return get_datetime(value).replace(tzinfo=ZoneInfo(get_system_timezone())).isoformat()


def closes_at_iso(request) -> str | None:
	return as_iso(closes_at(request))


def closing_passed(request) -> bool:
	closing = closes_at(request)
	return bool(closing) and now_datetime() >= closing


def is_closed(request) -> bool:
	return closing_passed(request) or bool(cint(request.get("quotes_opened")))


def is_open_bid(request) -> bool:
	return request.get("bidding_method") == OPEN_BID


def is_sealed(request) -> bool:
	return request.get("bidding_method") == SEALED_BID and not cint(request.get("quotes_opened"))
