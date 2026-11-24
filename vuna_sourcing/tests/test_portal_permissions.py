# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import json
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.permissions import update_permission_property
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from vuna_sourcing.api.portal import get_session
from vuna_sourcing.api.transactions.access import guard_portal_printing
from vuna_sourcing.api.transactions.customer import (
	get_dashboard,
	get_sales_invoices,
	get_sales_order,
	get_sales_orders,
)
from vuna_sourcing.api.transactions.customer_orders import delete_order, save_order
from vuna_sourcing.api.transactions.supplier import get_purchase_orders, get_rfq, save_quote
from vuna_sourcing.setup.app_setup import APPLIED_PERMISSIONS_KEY, apply_portal_permission_defaults
from vuna_sourcing.tests import make_test_user
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures

CUSTOMER_ROLE = "Customer"
SUPPLIER_ROLE = "Supplier"
SALES_ORDER = "Sales Order"
SALES_INVOICE = "Sales Invoice"
SUPPLIER_QUOTATION = "Supplier Quotation"
PURCHASE_ORDER = "Purchase Order"
DOWNLOAD_PDF = "/api/method/frappe.utils.print_format.download_pdf"
MULTI_PDF = "/api/method/frappe.utils.print_format.download_multi_pdf"
ORDERS_SETTING = "allow_customer_sales_orders"


class TestPortalPermissions(SourcingFixtures, IntegrationTestCase):
	"""Portal endpoints follow the role permissions set in Role Permission Manager."""

	def setUp(self):
		apply_portal_permission_defaults()
		current = frappe.db.get_single_value("Sourcing Settings", ORDERS_SETTING)
		self.addCleanup(frappe.db.set_single_value, "Sourcing Settings", ORDERS_SETTING, current)
		frappe.db.set_single_value("Sourcing Settings", ORDERS_SETTING, 1)
		self.customer, self.customer_user = self.make_customer()

	def set_right(self, doctype: str, role: str, right: str, value: int):
		update_permission_property(doctype, role, 0, right, value, validate=False)
		frappe.local.role_permissions = {}

	def revoke(self, doctype: str, role: str, right: str):
		self.set_right(doctype, role, right, 0)
		self.addCleanup(self.set_right, doctype, role, right, 1)

	def submitted_order(self, customer: str):
		doc = frappe.get_doc(
			{
				"doctype": SALES_ORDER,
				"customer": customer,
				"company": self.company,
				"transaction_date": nowdate(),
				"delivery_date": add_days(nowdate(), 7),
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"rate": 100,
						"uom": "Nos",
						"conversion_factor": 1,
						"warehouse": self.warehouse,
						"delivery_date": add_days(nowdate(), 7),
					}
				],
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
		doc.submit()
		return doc

	def print_request(self, path: str, doctype: str, user: str):
		request = SimpleNamespace(path=path)
		with self.set_user(user), patch.object(frappe.local, "request", request, create=True):
			frappe.local.form_dict.doctype = doctype
			guard_portal_printing()

	def test_a_customer_without_read_on_sales_orders_cannot_list_or_open_them(self):
		"""Taking Read off Sales Order for the Customer role closes the order list and detail."""
		order = self.submitted_order(self.customer)
		self.revoke(SALES_ORDER, CUSTOMER_ROLE, "read")

		with self.set_user(self.customer_user):
			self.assertRaisesRegex(frappe.PermissionError, "not allowed to view", get_sales_orders)
			self.assertRaisesRegex(frappe.PermissionError, "not allowed to view", get_sales_order, order.name)

	def test_a_customer_with_read_still_sees_their_orders(self):
		"""With the default rights the customer lists and opens their own submitted order."""
		order = self.submitted_order(self.customer)

		with self.set_user(self.customer_user):
			listed = [row["name"] for row in get_sales_orders()["rows"]]
			detail = get_sales_order(order.name)

		self.assertEqual(listed, [order.name])
		self.assertEqual(detail["name"], order.name)

	def test_rights_never_open_another_customers_order(self):
		"""Having every right on Sales Order does not reach a document of another customer."""
		other, _user = self.make_customer()
		theirs = self.submitted_order(other)

		with self.set_user(self.customer_user):
			self.assertRaises(frappe.PermissionError, get_sales_order, theirs.name)

	def test_a_customer_without_read_on_invoices_gets_no_invoice_figures(self):
		"""Without Read on Sales Invoice the invoice list refuses and the dashboard leaves invoices out."""
		self.revoke(SALES_INVOICE, CUSTOMER_ROLE, "read")

		with self.set_user(self.customer_user):
			self.assertRaises(frappe.PermissionError, get_sales_invoices)
			dashboard = get_dashboard(self.customer)

		self.assertIsNone(dashboard["balance"])
		self.assertEqual(dashboard["invoiced_by_month"], [])
		self.assertEqual(dashboard["invoices_by_status"], [])

	def test_a_customer_without_create_on_sales_orders_cannot_start_an_order(self):
		"""Without Create on Sales Order a new order is refused and the portal stops offering one."""
		self.revoke(SALES_ORDER, CUSTOMER_ROLE, "create")

		with self.set_user(self.customer_user):
			self.assertRaisesRegex(
				frappe.PermissionError,
				"not allowed to create",
				save_order,
				customer=self.customer,
				items=[{"item_code": self.item, "qty": 1, "uom": "Nos"}],
			)
			self.assertFalse(get_sales_orders(customer=self.customer)["can_order"])

	def test_a_customer_without_delete_cannot_discard_a_draft(self):
		"""Without Delete on Sales Order discarding a draft is refused before the draft is looked up."""
		self.revoke(SALES_ORDER, CUSTOMER_ROLE, "delete")

		with self.set_user(self.customer_user):
			self.assertRaisesRegex(
				frappe.PermissionError, "not allowed to delete", delete_order, self.customer, "SAL-ORD-NONE"
			)

	def test_a_supplier_without_create_on_supplier_quotations_cannot_quote(self):
		"""Without Create on Supplier Quotation a supplier can read the RFQ but cannot save a quote."""
		supplier, user = self.make_supplier()
		rfq = self.make_rfq([supplier])
		self.revoke(SUPPLIER_QUOTATION, SUPPLIER_ROLE, "create")

		with self.set_user(user):
			detail = get_rfq(rfq.name)
			self.assertRaisesRegex(
				frappe.PermissionError, "not allowed to create", save_quote, rfq.name, items=[]
			)

		self.assertFalse(detail["can_quote"])

	def test_a_supplier_without_read_on_purchase_orders_cannot_list_them(self):
		"""Without Read on Purchase Order the supplier's order list is refused."""
		_supplier, user = self.make_supplier()
		self.revoke(PURCHASE_ORDER, SUPPLIER_ROLE, "read")

		with self.set_user(user):
			self.assertRaisesRegex(frappe.PermissionError, "not allowed to view", get_purchase_orders)

	def test_printing_is_refused_without_the_print_right(self):
		"""Frappe's PDF download refuses a portal user whose role has Read but not Print."""
		self.revoke(SALES_ORDER, CUSTOMER_ROLE, "print")

		self.assertRaisesRegex(
			frappe.PermissionError,
			"not allowed to print",
			self.print_request,
			DOWNLOAD_PDF,
			SALES_ORDER,
			self.customer_user,
		)

	def test_printing_is_allowed_with_the_print_right(self):
		"""With Print on the role the PDF download goes ahead to Frappe's own checks."""
		self.print_request(DOWNLOAD_PDF, SALES_ORDER, self.customer_user)

	def test_multi_document_printing_checks_every_doctype(self):
		"""A bulk PDF request naming a doctype without Print is refused too."""
		self.revoke(SALES_ORDER, CUSTOMER_ROLE, "print")

		self.assertRaises(
			frappe.PermissionError,
			self.print_request,
			MULTI_PDF,
			json.dumps({SALES_ORDER: ["SAL-ORD-NONE"]}),
			self.customer_user,
		)

	def test_staff_printing_is_not_limited_by_portal_rights(self):
		"""Desk staff keep printing when the portal role loses Print."""
		staff = make_test_user(["Sales User"], first_name="Sales").name
		self.revoke(SALES_ORDER, CUSTOMER_ROLE, "print")

		self.print_request(DOWNLOAD_PDF, SALES_ORDER, staff)

	def test_portal_users_cannot_change_documents_through_the_framework(self):
		"""Write on the role does not let a portal user edit or cancel through the REST API."""
		order = self.submitted_order(self.customer)

		with self.set_user(self.customer_user):
			self.assertTrue(frappe.has_permission(SALES_ORDER, "read", doc=order.name))
			for right in ("write", "cancel", "delete"):
				self.assertFalse(frappe.has_permission(SALES_ORDER, right, doc=order.name), right)

	def test_the_session_lists_the_rights_for_the_users_party_types(self):
		"""The session carries rights only for the user's own party types and follows revoked rights."""
		self.revoke(SALES_ORDER, CUSTOMER_ROLE, "print")

		with self.set_user(self.customer_user):
			rights = get_session()["permissions"]

		self.assertNotIn(PURCHASE_ORDER, rights)
		self.assertTrue(rights[SALES_ORDER]["read"])
		self.assertFalse(rights[SALES_ORDER]["print"])

	def test_defaults_are_applied_once_and_keep_later_changes(self):
		"""Running migrate again does not switch back on a right an admin turned off."""
		self.revoke(SALES_ORDER, CUSTOMER_ROLE, "print")

		apply_portal_permission_defaults()
		frappe.local.role_permissions = {}

		with self.set_user(self.customer_user):
			self.assertFalse(frappe.has_permission(SALES_ORDER, "print"))

	def test_defaults_are_granted_where_they_were_never_applied(self):
		"""A role and doctype pair that never had the defaults gets them on the next migrate."""
		applied = frappe.db.get_global(APPLIED_PERMISSIONS_KEY)
		self.addCleanup(frappe.db.set_global, APPLIED_PERMISSIONS_KEY, applied)
		self.revoke(SALES_ORDER, CUSTOMER_ROLE, "print")
		remaining = [key for key in json.loads(applied) if key != f"{SALES_ORDER}::{CUSTOMER_ROLE}"]
		frappe.db.set_global(APPLIED_PERMISSIONS_KEY, json.dumps(remaining))

		apply_portal_permission_defaults()
		frappe.local.role_permissions = {}

		with self.set_user(self.customer_user):
			self.assertTrue(frappe.has_permission(SALES_ORDER, "print"))
