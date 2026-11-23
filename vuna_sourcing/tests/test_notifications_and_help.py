# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from vuna_sourcing.api.portal import get_session
from vuna_sourcing.api.transactions import award
from vuna_sourcing.tests.sourcing_fixtures import SourcingFixtures
from vuna_sourcing.utils import HELPDESK_NEW_TICKET, notification_sender

SETTINGS = "Sourcing Settings"
ACCOUNT_FIELD = "notification_email_account"


def make_email_account(outgoing: bool) -> frappe._dict:
	suffix = frappe.generate_hash(length=6)
	email = f"portal-{suffix}@example.com"
	doc = frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_account_name": f"_Test Portal Mail {suffix}",
			"email_id": email,
			"enable_outgoing": int(outgoing),
			"enable_incoming": 0,
			"smtp_server": "smtp.example.com",
			"smtp_port": 587,
			"no_smtp_authentication": 1,
		}
	).insert(ignore_permissions=True)
	return frappe._dict(name=doc.name, email=email, title=doc.email_account_name)


class TestNotificationEmailAccount(SourcingFixtures, IntegrationTestCase):
	"""Sourcing Settings chooses the outgoing account portal emails are sent from."""

	def setUp(self):
		current = frappe.db.get_single_value(SETTINGS, ACCOUNT_FIELD)
		self.addCleanup(frappe.db.set_single_value, SETTINGS, ACCOUNT_FIELD, current)
		frappe.db.set_single_value(SETTINGS, ACCOUNT_FIELD, None)

	def choose(self, account: str | None):
		settings = frappe.get_single(SETTINGS)
		settings.set(ACCOUNT_FIELD, account)
		settings.save(ignore_permissions=True)

	def test_an_account_that_cannot_send_email_is_refused(self):
		"""Saving Sourcing Settings with an Email Account that has Enable Outgoing off fails."""
		incoming_only = make_email_account(outgoing=False)

		self.assertRaisesRegex(frappe.ValidationError, "cannot send email", self.choose, incoming_only.name)
		self.assertFalse(frappe.db.get_single_value(SETTINGS, ACCOUNT_FIELD))

	def test_an_outgoing_account_can_be_chosen(self):
		"""An Email Account with Enable Outgoing on is saved and becomes the portal sender."""
		account = make_email_account(outgoing=True)

		self.choose(account.name)

		self.assertEqual(frappe.db.get_single_value(SETTINGS, ACCOUNT_FIELD), account.name)
		self.assertEqual(notification_sender(), f"{account.title} <{account.email}>")

	def test_portal_emails_are_queued_from_the_chosen_account(self):
		"""Award notices go out from the chosen account rather than the site default."""
		account = make_email_account(outgoing=True)
		self.choose(account.name)
		reference = "_Test RFQ " + frappe.generate_hash(length=6)

		with patch.object(award, "recipients_of", return_value=["jane.doe@example.com"]):
			award.notify_supplier(reference, "_Test Supplier", "Your quote", "<p>Results are in.</p>")

		queued = frappe.get_all(
			"Email Queue",
			filters={"reference_name": reference},
			fields=["sender", "email_account"],
		)
		self.assertEqual(len(queued), 1)
		self.assertIn(account.email, queued[0].sender)
		self.assertEqual(queued[0].email_account, account.name)

	def test_without_a_chosen_account_the_site_default_is_used(self):
		"""With no account chosen, portal emails leave the sender to the site's default outgoing account."""
		self.assertIsNone(notification_sender())

	def test_an_account_that_stops_sending_falls_back_to_the_site_default(self):
		"""If the chosen account later has Enable Outgoing turned off, portal emails use the site default."""
		account = make_email_account(outgoing=True)
		self.choose(account.name)

		frappe.db.set_value("Email Account", account.name, "enable_outgoing", 0)

		self.assertIsNone(notification_sender())


class TestHelpDeskLink(SourcingFixtures, IntegrationTestCase):
	"""The portal offers a help desk link only on sites with Helpdesk installed."""

	def setUp(self):
		_customer, self.user = self.make_customer()

	def session_help_url(self, installed_apps: list[str]):
		with patch("vuna_sourcing.utils.get_installed_apps", return_value=installed_apps):
			with self.set_user(self.user):
				return get_session()["help_url"]

	def test_the_help_link_opens_a_new_ticket_when_helpdesk_is_installed(self):
		"""A portal user on a site with Helpdesk gets the new-ticket link."""
		url = self.session_help_url(["frappe", "erpnext", "vuna_sourcing", "helpdesk"])

		self.assertEqual(url, HELPDESK_NEW_TICKET)

	def test_there_is_no_help_link_without_helpdesk(self):
		"""Without Helpdesk installed the portal gets no help link, so the Help section stays hidden."""
		url = self.session_help_url(["frappe", "erpnext", "vuna_sourcing"])

		self.assertIsNone(url)

	def test_a_guest_cannot_read_the_session(self):
		"""The session, and the help link with it, is only for signed-in users."""
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, get_session)
