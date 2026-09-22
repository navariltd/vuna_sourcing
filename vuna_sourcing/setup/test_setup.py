# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime

from vuna_sourcing.install import apply_single_defaults


def before_tests():
	frappe.clear_cache()

	if not frappe.db.a_row_exists("Company"):
		from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

		year = now_datetime().year
		setup_complete(
			{
				"currency": "KES",
				"full_name": "Test User",
				"company_name": "_Test Vuna Company",
				"timezone": "Africa/Nairobi",
				"company_abbr": "_TVC",
				"industry": "Manufacturing",
				"country": "Kenya",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@example.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)

		if not frappe.db.a_row_exists("Company"):
			frappe.throw(_("ERPNext setup wizard did not create a Company; see the Error Log for the cause."))

	apply_single_defaults("Sourcing Settings")
	frappe.db.commit()  # nosemgrep
