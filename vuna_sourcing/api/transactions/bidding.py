# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from datetime import datetime, time

from frappe.utils import cint, get_datetime, getdate, now_datetime

SEALED_BID = "Sealed Bid"


def closes_at(request) -> datetime | None:
	if request.get("bid_closing"):
		return get_datetime(request.bid_closing)
	if request.get("schedule_date"):
		return datetime.combine(getdate(request.schedule_date), time.max)
	return None


def is_closed(request) -> bool:
	closing = closes_at(request)
	return bool(closing) and now_datetime() >= closing


def is_sealed(request) -> bool:
	return request.get("bidding_method") == SEALED_BID and not cint(request.get("quotes_opened"))
