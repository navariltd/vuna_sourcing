import frappe


def make_test_user(roles=(), **fields):
	"""Insert a fixture User, bypassing Frappe's signup throttle.

	User.before_insert refuses once more than `throttle_user_limit` (60) users were
	created in the last hour; test classes only roll back at teardown, so a busy class
	trips it. The throttle is skipped during imports, which fixtures effectively are.
	"""
	in_import = frappe.flags.in_import
	frappe.flags.in_import = True
	try:
		return frappe.get_doc(
			{
				"doctype": "User",
				"email": f"{frappe.generate_hash(length=10)}@example.com",
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
				**fields,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.flags.in_import = in_import
