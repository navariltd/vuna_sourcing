# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from datetime import datetime, time
from zoneinfo import ZoneInfo

from frappe.utils import cint, get_datetime, get_system_timezone, getdate, now_datetime

SEALED_BID = "Sealed Bid"


def closes_at(request) -> datetime | None:
	if request.get("bid_closing"):
		return get_datetime(request.bid_closing)
	if request.get("schedule_date"):
		return datetime.combine(getdate(request.schedule_date), time.max)
	return None


def closes_at_iso(request) -> str | None:
	closing = closes_at(request)
	if not closing:
		return None
	return closing.replace(tzinfo=ZoneInfo(get_system_timezone())).isoformat()


def closing_passed(request) -> bool:
	closing = closes_at(request)
	return bool(closing) and now_datetime() >= closing


def is_closed(request) -> bool:
	return closing_passed(request) or bool(cint(request.get("quotes_opened")))


def is_sealed(request) -> bool:
	return request.get("bidding_method") == SEALED_BID and not cint(request.get("quotes_opened"))
