# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

from dataclasses import dataclass

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, escape_html, validate_email_address

from vuna_sourcing.api.permission import PORTAL_USER_ROLE
from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.utils import get_app_branding, get_open_party_types

OPEN_TO_PUBLIC = "Open to Public"


@dataclass
class SignupContext:
	is_open: bool
	app_title: str | None
	logo: str | None
	contact_email: str | None
	closed_message: str | None
	party_types: list[str]


@dataclass
class SignupResult:
	email: str
	email_sent: bool = False


def get_contact_email() -> str | None:
	return frappe.db.get_single_value("Sourcing Settings", "contact_email")


def invitation_only_message() -> str:
	return _(
		"We take on new suppliers and customers by invitation at the moment. Please get in "
		"touch with your contact on our team and they will send you an invitation to apply."
	)


def registration_is_open() -> bool:
	settings = frappe.get_cached_doc("Sourcing Settings")
	return settings.registration_mode == OPEN_TO_PUBLIC and bool(get_open_party_types())


@frappe.whitelist(allow_guest=True)  # nosemgrep
def get_signup_context() -> ApiResponse[SignupContext]:
	is_open = registration_is_open()
	branding = get_app_branding()

	return ApiResponse.success(
		data=SignupContext(
			is_open=is_open,
			app_title=branding["title"],
			logo=branding["logo"],
			contact_email=get_contact_email(),
			closed_message=None if is_open else invitation_only_message(),
			party_types=get_open_party_types() if is_open else [],
		)
	)


def can_invite() -> bool:
	return frappe.session.user != "Guest" and bool(frappe.has_permission("Sourcing Settings", "write"))


def signups_allowed_per_hour() -> int:
	return 300 if can_invite() else 5


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep
@rate_limit(limit=signups_allowed_per_hour, seconds=60 * 60, ip_based=True)
def sign_up(first_name: str, last_name: str, email: str) -> ApiResponse[SignupResult]:
	if not (registration_is_open() or can_invite()):
		return ApiResponse.error(invitation_only_message())

	first_name = (first_name or "").strip()
	last_name = (last_name or "").strip()
	email = (email or "").strip().lower()

	if not first_name:
		frappe.throw(_("Please tell us your first name."), title=_("First name needed"))
	if not last_name:
		frappe.throw(_("Please tell us your last name."), title=_("Last name needed"))
	if not email or not validate_email_address(email):
		frappe.throw(
			_("That does not look like a valid email address."),
			title=_("Check your email address"),
		)

	existing = frappe.db.get_value("User", {"email": email}, ["name", "enabled"], as_dict=True)
	if existing:
		if existing.enabled:
			return ApiResponse.error(
				_(
					"There is already an account for {0}. Sign in instead — or reset your "
					"password if you have forgotten it."
				).format(email),
				SignupResult(email=email),
			)
		return ApiResponse.error(
			_("An account for {0} exists but has been disabled. Please contact our team.").format(email),
			SignupResult(email=email),
		)

	_check_signup_ceiling()

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": escape_html(first_name),
			"last_name": escape_html(last_name),
			"enabled": 1,
			"user_type": "Website User",
			"send_welcome_email": 1,
			"roles": [{"role": PORTAL_USER_ROLE}],
		}
	)

	user.flags.ignore_permissions = True
	user.insert()

	email_sent = bool(user.flags.email_sent)

	if email_sent:
		message = _(
			"Account created. We have sent a link to {0} — open it to set your password, "
			"then you can start your application."
		).format(email)
	else:
		message = _(
			"Your account for {0} was created, but we could not send the setup email. "
			"Please contact our team and they will activate it for you."
		).format(email)

	return ApiResponse.success(message, SignupResult(email=email, email_sent=email_sent))


def _check_signup_ceiling():
	ceiling = cint(frappe.get_system_settings("max_signups_allowed_per_hour") or 300)
	if frappe.db.get_creation_count("User", 60) >= ceiling:
		frappe.throw(
			_("Too many accounts have been created in the past hour. Please try again shortly."),
			title=_("Temporarily unavailable"),
		)
