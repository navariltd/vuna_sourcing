import frappe


def make_test_user(roles=(), **fields):
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
