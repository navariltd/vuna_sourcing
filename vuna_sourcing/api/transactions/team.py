# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.permissions import AUTOMATIC_ROLES
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, cstr, escape_html, validate_email_address

from vuna_sourcing.api.permission import PORTAL_ROLES, PORTAL_USER_ROLE
from vuna_sourcing.api.portal import PARTY_ROLE, check_party_access
from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.api.transactions.branches import (
	ACCOUNT_ADMIN_FIELD,
	BRANCHES_FIELD,
	PORTAL_USER,
	branch_title,
	join_branches,
	linked_addresses,
	parse_branches,
)
from vuna_sourcing.utils import CUSTOMER

SETTING = "allow_customer_team_management"
PORTAL_USERS_FIELD = "portal_users"
USER = "User"
WEBSITE_USER = "Website User"
INVITED = "Invited"
ACTIVE = "Active"
DISABLED = "Disabled"
NAME_LENGTH = 80
MAX_BRANCHES = 200
INVITES_PER_HOUR = 30


def team_management_enabled() -> bool:
	return bool(cint(frappe.db.get_single_value("Sourcing Settings", SETTING)))


def ensure_enabled() -> None:
	if not team_management_enabled():
		frappe.throw(_("Managing your team on the portal is turned off."), frappe.PermissionError)


def admin_customers(user: str | None = None) -> set[str]:
	return set(
		frappe.get_all(
			PORTAL_USER,
			filters={"parenttype": CUSTOMER, "user": user or frappe.session.user, ACCOUNT_ADMIN_FIELD: 1},
			pluck="parent",
		)
	)


def is_account_admin(customer: str, user: str | None = None) -> bool:
	return customer in admin_customers(user)


def deny_non_admin(customer: str) -> None:
	frappe.throw(
		_("Only an account admin of {0} can manage its users.").format(customer), frappe.PermissionError
	)


def managed_customer(customer: str | None) -> str:
	ensure_enabled()
	if not customer:
		frappe.throw(_("Choose the customer account whose team you want to manage."))

	check_party_access(CUSTOMER, customer)
	if not is_account_admin(customer):
		deny_non_admin(customer)

	return customer


def locked_customer(customer: str | None):
	doc = frappe.get_doc(CUSTOMER, managed_customer(customer), for_update=True)
	if not any(row.user == frappe.session.user and row.get(ACCOUNT_ADMIN_FIELD) for row in doc.portal_users):
		deny_non_admin(doc.name)

	if doc.disabled:
		frappe.throw(_("{0} is disabled, so its team cannot be changed.").format(doc.name))

	return doc


def managed_row(doc, user: str | None):
	row = next((row for row in doc.portal_users if row.user == cstr(user).strip()), None)
	if not row:
		frappe.throw(_("{0} is not on your team.").format(cstr(user)))

	if row.user == frappe.session.user:
		frappe.throw(_("You cannot change your own access. Ask another account admin or our team."))

	if row.get(ACCOUNT_ADMIN_FIELD):
		frappe.throw(_("{0} is an account admin. Ask our team to change their access.").format(row.user))

	return row


def chosen_branches(customer: str, branches: list | str | None) -> list[str]:
	names = frappe.parse_json(branches) if isinstance(branches, str) else branches or []
	if not isinstance(names, list):
		frappe.throw(_("Your branch choice could not be read. Refresh the page and try again."))

	if len(names) > MAX_BRANCHES:
		frappe.throw(_("Choose up to {0} branches, or leave it empty for every branch.").format(MAX_BRANCHES))

	chosen = list(dict.fromkeys(cstr(name).strip() for name in names if cstr(name).strip()))
	if not chosen:
		return []

	shipping = {
		address.name
		for address in linked_addresses([customer], enabled_only=True, shipping_only=True, names=chosen)
	}
	if any(name not in shipping for name in chosen):
		frappe.throw(_("One of the branches you picked is not a delivery address of {0}.").format(customer))

	return chosen


def person_name(value: str | None, label: str) -> str:
	name = cstr(value).strip()
	if not name:
		frappe.throw(_("Enter their {0}.").format(label))

	if len(name) > NAME_LENGTH:
		frappe.throw(_("Their {0} can be at most {1} characters.").format(label, NAME_LENGTH))

	return escape_html(name)


def invitee_email(doc, email: str | None) -> str:
	email = cstr(email).strip().lower()
	if not email or not validate_email_address(email):
		frappe.throw(_("That does not look like a valid email address."))

	if any(row.user == email for row in doc.portal_users):
		frappe.throw(_("{0} is already on your team.").format(email))

	if frappe.db.exists(USER, email) or frappe.db.exists(USER, {"email": email}):
		frappe.throw(
			_(
				"There is already an account for {0}. Ask our team to add it to {1}, or invite a different email address."
			).format(email, doc.name)
		)

	return email


def member_view(row, user: dict | None, titles: dict[str, str]) -> dict:
	branches = parse_branches(row.get(BRANCHES_FIELD))
	user = user or {}
	if user.get("enabled") == 0:
		status = DISABLED
	elif user.get("last_login"):
		status = ACTIVE
	else:
		status = INVITED

	return {
		"user": row.user,
		"full_name": user.get("full_name") or row.user,
		"image": user.get("user_image"),
		"is_account_admin": bool(row.get(ACCOUNT_ADMIN_FIELD)),
		"is_you": row.user == frappe.session.user,
		"status": status,
		"all_branches": not branches,
		"branches": [{"name": name, "title": titles.get(name, name)} for name in branches],
		"editable": row.user != frappe.session.user and not row.get(ACCOUNT_ADMIN_FIELD),
	}


def team_view(customer: str, rows) -> list[dict]:
	emails = [row.user for row in rows]
	users = {
		user.name: user
		for user in frappe.get_all(
			USER,
			filters={"name": ("in", emails or [""])},
			fields=["name", "full_name", "user_image", "last_login", "enabled"],
		)
	}
	titles = {address.name: branch_title(address) for address in linked_addresses([customer])}

	members = [member_view(row, users.get(row.user), titles) for row in rows]
	members.sort(
		key=lambda member: (not member["is_you"], not member["is_account_admin"], member["full_name"])
	)
	return members


def save_team(doc, note: str) -> None:
	doc.flags.ignore_permissions = True
	doc.save()
	doc.add_comment("Info", note)


def disable_if_unlinked(user: str) -> None:
	if frappe.db.exists(PORTAL_USER, {"user": user}):
		return

	if set(frappe.get_roles(user)) - set(AUTOMATIC_ROLES) - set(PORTAL_ROLES):
		return

	account = frappe.get_doc(USER, user)
	account.enabled = 0
	account.flags.ignore_permissions = True
	account.save()


@frappe.whitelist()
def get_team(customer: str) -> ApiResponse[dict]:
	customer = managed_customer(customer)
	rows = frappe.get_all(
		PORTAL_USER,
		filters={"parenttype": CUSTOMER, "parent": customer},
		fields=["user", BRANCHES_FIELD, ACCOUNT_ADMIN_FIELD],
		order_by="idx asc",
	)

	return ApiResponse.success(data={"customer": customer, "members": team_view(customer, rows)})


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=INVITES_PER_HOUR, seconds=60 * 60, ip_based=False, user_based=True)
def invite_team_member(
	customer: str,
	first_name: str | None = None,
	last_name: str | None = None,
	email: str | None = None,
	branches: list | str | None = None,
) -> ApiResponse[dict]:
	doc = locked_customer(customer)
	first_name = person_name(first_name, _("first name"))
	last_name = person_name(last_name, _("last name"))
	email = invitee_email(doc, email)
	chosen = chosen_branches(doc.name, branches)

	account = frappe.get_doc(
		{
			"doctype": USER,
			"email": email,
			"first_name": first_name,
			"last_name": last_name,
			"enabled": 1,
			"user_type": WEBSITE_USER,
			"send_welcome_email": 1,
			"roles": [{"role": PORTAL_USER_ROLE}, {"role": PARTY_ROLE[CUSTOMER]}],
		}
	)
	account.flags.ignore_permissions = True
	account.insert()

	doc.append(PORTAL_USERS_FIELD, {"user": account.name, BRANCHES_FIELD: join_branches(chosen) or None})
	save_team(doc, _("{0} invited {1} to the portal.").format(frappe.session.user, account.name))
	frappe.clear_messages()

	message = (
		_("Invitation sent to {0}. They get an email to set a password and sign in.").format(email)
		if account.flags.email_sent
		else _(
			"{0} was added, but the invitation email could not be sent. Ask our team to resend it."
		).format(email)
	)
	return ApiResponse.success(message, {"members": team_view(doc.name, doc.portal_users)})


@frappe.whitelist(methods=["POST"])
def update_member_branches(customer: str, user: str, branches: list | str | None = None) -> ApiResponse[dict]:
	doc = locked_customer(customer)
	row = managed_row(doc, user)
	row.set(BRANCHES_FIELD, join_branches(chosen_branches(doc.name, branches)) or None)
	save_team(doc, _("{0} changed the branches {1} can see.").format(frappe.session.user, row.user))

	return ApiResponse.success(
		_("Branches updated for {0}.").format(row.user), {"members": team_view(doc.name, doc.portal_users)}
	)


@frappe.whitelist(methods=["POST"])
def remove_team_member(customer: str, user: str) -> ApiResponse[dict]:
	doc = locked_customer(customer)
	row = managed_row(doc, user)
	removed = row.user
	doc.remove(row)
	save_team(doc, _("{0} removed {1} from the portal team.").format(frappe.session.user, removed))
	disable_if_unlinked(removed)

	return ApiResponse.success(
		_("{0} no longer has access to {1}.").format(removed, doc.name),
		{"members": team_view(doc.name, doc.portal_users)},
	)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=INVITES_PER_HOUR, seconds=60 * 60, ip_based=False, user_based=True)
def resend_invitation(customer: str, user: str) -> ApiResponse[None]:
	doc = locked_customer(customer)
	row = managed_row(doc, user)

	account = frappe.get_doc(USER, row.user)
	if account.last_login:
		return ApiResponse.error(
			_("{0} has already signed in, so there is no invitation to resend.").format(row.user)
		)
	if not account.enabled:
		return ApiResponse.error(
			_("{0} is disabled. Ask our team to turn the account back on.").format(row.user)
		)

	account.send_welcome_mail_to_user()
	return ApiResponse.success(_("Invitation sent again to {0}.").format(row.user))
