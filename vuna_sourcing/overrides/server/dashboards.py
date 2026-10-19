# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from vuna_sourcing.api.transactions.bidding import AWARD


def with_award(data: dict) -> dict:
	items = data["transactions"][0]["items"]
	if AWARD not in items:
		items.append(AWARD)
	return data


def request_for_quotation(data: dict) -> dict:
	return with_award(data)


def supplier_quotation(data: dict) -> dict:
	return with_award(data)
