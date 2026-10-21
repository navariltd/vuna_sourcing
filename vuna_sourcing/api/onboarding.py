# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import base64

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

from vuna_sourcing.api.portal import get_current_user
from vuna_sourcing.api.response import ApiResponse
from vuna_sourcing.utils import PARTY_TYPES, get_open_party_types
from vuna_sourcing.vuna_sourcing.doctype.party_onboarding_request.party_onboarding_request import (
	DOCTYPE,
	PENDING_REVIEW,
	RETURNED,
	TEMPLATE_DOCTYPE,
	get_document_types_for,
)

APPLICANT_FIELDS = (
	"party_type",
	"onboarding_template",
	"party_name",
	"company_logo",
	"country",
	"tax_id",
	"registration_number",
	"website",
	"bank",
	"bank_account_no",
	"account_holder_name",
	"iban",
	"branch_code",
	"swift_number",
)

CONTACT_FIELDS = (
	"first_name",
	"last_name",
	"designation",
	"email_id",
	"mobile_no",
	"is_primary_contact",
	"is_billing_contact",
)

ADDRESS_FIELDS = (
	"address_type",
	"address_line1",
	"address_line2",
	"city",
	"state",
	"pincode",
	"country",
	"is_primary_address",
	"is_shipping_address",
)

PORTAL_ADDRESS_TYPES = ("Billing", "Shipping", "Office", "Warehouse", "Plant", "Shop")

DOCUMENT_FIELDS = (
	"document_type",
	"attachment",
	"document_number",
	"issue_date",
	"expiry_date",
)

LINK_OPTION_DOCTYPES = ("Country", "Bank")


def get_own_application(name: str, *, for_write: bool = False):
	user = get_current_user()

	owner = frappe.db.get_value(DOCTYPE, name, "owner")
	if not owner:
		frappe.throw(_("That application does not exist."), frappe.DoesNotExistError)

	if owner != user:
		frappe.throw(_("That application belongs to someone else."), frappe.PermissionError)

	doc = frappe.get_doc(DOCTYPE, name)

	if for_write and not is_editable(doc):
		frappe.throw(
			_("This application is with us for review and can no longer be edited."),
			title=_("Locked"),
		)

	return doc


def is_correction(doc) -> bool:
	return doc.docstatus == 1 and doc.onboarding_status == RETURNED


def is_editable(doc) -> bool:
	return doc.docstatus == 0 or is_correction(doc)


def apply_applicant_values(doc, values: dict):
	check_party_type_is_open(doc, values.get("party_type"))

	for field in APPLICANT_FIELDS:
		if field in values:
			doc.set(field, values.get(field))

	if doc.company_logo:
		check_is_own_upload(doc, doc.company_logo)

	if "contacts" in values:
		_replace_rows(doc, "contacts", values.get("contacts"), CONTACT_FIELDS)
	if "addresses" in values:
		_replace_rows(doc, "addresses", values.get("addresses"), ADDRESS_FIELDS)
		for row in doc.addresses:
			if row.address_type not in PORTAL_ADDRESS_TYPES:
				row.address_type = "Billing"

	_apply_documents(doc, values.get("documents"))


def check_party_type_is_open(doc, party_type: str | None):
	if not party_type or party_type == doc.party_type:
		return

	if party_type not in PARTY_TYPES or party_type not in get_open_party_types():
		frappe.throw(
			_("We are not taking {0} applications at the moment.").format(_(party_type or "").lower()),
			title=_("Not Accepting Applications"),
		)


def _replace_rows(doc, table: str, rows, allowed: tuple[str, ...]):
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)

	doc.set(table, [])
	for incoming in rows or []:
		doc.append(table, {field: incoming.get(field) for field in allowed if field in incoming})


def get_default_company() -> str | None:
	return frappe.defaults.get_defaults().get("company") or frappe.db.get_value(
		"Company", {}, "name", order_by="creation asc"
	)


@frappe.whitelist()
def get_onboarding_types() -> list[dict]:
	get_current_user()

	open_party_types = get_open_party_types()
	if not open_party_types:
		return []

	templates = frappe.get_all(
		TEMPLATE_DOCTYPE,
		filters={"disabled": 0, "party_type": ("in", open_party_types)},
		fields=[
			"name",
			"party_type",
			"entity_type",
			"description",
			"is_default",
			"require_tax_id",
			"require_registration_number",
			"require_bank_details",
			"require_shipping_address",
		],
		order_by="is_default desc, name asc",
	)

	usable = {party_type: set(get_document_types_for(party_type)) for party_type in open_party_types}

	for template in templates:
		rows = frappe.get_all(
			"Party Onboarding Document Requirement",
			filters={"parent": template.name, "parenttype": TEMPLATE_DOCTYPE},
			fields=["document_type", "is_mandatory", "description", "has_expiry"],
			order_by="idx asc",
		)
		template["documents"] = [r for r in rows if r.document_type in usable[template.party_type]]

	return templates


@frappe.whitelist()
def get_link_options(doctype: str, search: str | None = None) -> list[dict]:
	get_current_user()

	if doctype not in LINK_OPTION_DOCTYPES:
		frappe.throw(_("That cannot be looked up from the portal."), frappe.PermissionError)

	filters = {}
	if search:
		filters["name"] = ("like", f"%{search}%")

	names = frappe.get_all(doctype, filters=filters, pluck="name", order_by="name asc", limit=50)
	return [{"label": name, "value": name} for name in names]


@frappe.whitelist()
def get_upload_rules(document_type: str | None = None) -> dict:
	get_current_user()
	return frappe.get_cached_doc("Sourcing Settings").get_upload_rules(document_type)


@frappe.whitelist()
def get_my_applications() -> list[dict]:
	get_current_user()

	return frappe.get_all(
		DOCTYPE,
		filters={"owner": frappe.session.user},
		fields=[
			"name",
			"party_type",
			"party_name",
			"onboarding_template",
			"onboarding_status",
			"review_remarks",
			"party",
			"docstatus",
			"modified",
			"creation",
		],
		order_by="creation desc",
	)


def find_application_in_progress() -> str | None:
	user = frappe.session.user

	draft = frappe.db.get_value(DOCTYPE, {"owner": user, "docstatus": 0}, "name", order_by="creation desc")
	if draft:
		return draft

	return frappe.db.get_value(
		DOCTYPE,
		{"owner": user, "docstatus": 1, "onboarding_status": RETURNED},
		"name",
		order_by="creation desc",
	)


@frappe.whitelist()
def get_application(name: str | None = None) -> dict | None:
	get_current_user()

	if not name:
		name = find_application_in_progress()
		if not name:
			return None

	doc = get_own_application(name)
	rules = doc.document_rules()
	settings = frappe.get_cached_doc("Sourcing Settings")
	files = attached_files(doc)

	return {
		"name": doc.name,
		"docstatus": doc.docstatus,
		"onboarding_status": doc.onboarding_status,
		"review_remarks": doc.review_remarks,
		"party": doc.party,
		"entity_type": doc.entity_type,
		"can_edit": is_editable(doc),
		"is_correction": is_correction(doc),
		**{field: doc.get(field) for field in APPLICANT_FIELDS},
		"contacts": [{field: row.get(field) for field in ("idx", *CONTACT_FIELDS)} for row in doc.contacts],
		"addresses": [{field: row.get(field) for field in ("idx", *ADDRESS_FIELDS)} for row in doc.addresses],
		"documents": [
			{
				"idx": row.idx,
				"document_type": row.document_type,
				"is_mandatory": row.is_mandatory,
				"has_expiry": rules[row.document_type].has_expiry,
				"description": row.description,
				**settings.get_upload_rules(row.document_type),
				"attachment": row.attachment,
				"file_name": files.get(row.attachment, {}).get("file_name"),
				"file_size": files.get(row.attachment, {}).get("file_size"),
				"document_number": row.document_number,
				"issue_date": row.issue_date,
				"expiry_date": row.expiry_date,
			}
			for row in doc.required_documents
		],
	}


def attached_files(doc) -> dict[str, dict]:
	urls = [row.attachment for row in doc.required_documents if row.attachment]
	if not urls:
		return {}
	return {
		row.file_url: row
		for row in frappe.get_all(
			"File",
			filters={"attached_to_doctype": DOCTYPE, "attached_to_name": doc.name, "file_url": ("in", urls)},
			fields=["file_url", "file_name", "file_size"],
		)
	}


def _save(doc):
	doc.flags.ignore_mandatory = True
	doc.flags.ignore_permissions = True
	doc.flags.silent_outstanding = True

	if doc.docstatus == 1:
		doc.flags.ignore_validate_update_after_submit = True

	doc.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def save_application(values: dict | str, name: str | None = None) -> dict:
	get_current_user()

	if isinstance(values, str):
		values = frappe.parse_json(values)

	if name:
		doc = get_own_application(name, for_write=True)
	else:
		doc = frappe.new_doc(DOCTYPE)
		doc.company = get_default_company()
		doc.applicant_user = frappe.session.user

	apply_applicant_values(doc, values)
	_save(doc)

	return get_application(doc.name)


@frappe.whitelist(methods=["POST"])
def resubmit_application(name: str, values: dict | str | None = None) -> dict:
	doc = get_own_application(name, for_write=True)

	if not is_correction(doc):
		frappe.throw(
			_("Only an application we have sent back for correction can be resubmitted."),
			title=_("Nothing to resubmit"),
		)

	if isinstance(values, str):
		values = frappe.parse_json(values)

	if values:
		apply_applicant_values(doc, values)

	_save(doc)

	doc.validate_mandatory_documents()

	doc.db_set(
		{
			"onboarding_status": PENDING_REVIEW,
			"review_remarks": None,
			"reviewed_by": None,
			"reviewed_on": None,
		}
	)
	doc.add_comment("Comment", _("<b>Resubmitted for review</b>"))

	return get_application(doc.name)


def _apply_documents(doc, documents):
	if not documents:
		return

	if isinstance(documents, str):
		documents = frappe.parse_json(documents)

	supplied = {row.get("document_type"): row for row in documents if row.get("document_type")}

	for row in doc.required_documents:
		incoming = supplied.get(row.document_type)
		if not incoming:
			continue

		for field in DOCUMENT_FIELDS:
			if field == "document_type" or field not in incoming:
				continue
			row.set(field, incoming.get(field) or None)

		if row.attachment:
			check_is_own_upload(doc, row.attachment)


def check_is_own_upload(doc, file_url: str):
	if doc.is_new() or not frappe.db.exists(
		"File", {"file_url": file_url, "attached_to_doctype": DOCTYPE, "attached_to_name": doc.name}
	):
		frappe.throw(
			_("That file was not uploaded to this application. Please upload it again."),
			title=_("Unknown File"),
		)


@frappe.whitelist(methods=["POST"])
def submit_application(name: str) -> dict:
	get_current_user()

	doc = get_own_application(name, for_write=True)

	if is_correction(doc):
		return resubmit_application(name)

	if doc.party_type not in get_open_party_types():
		frappe.throw(
			_("We are not taking {0} applications at the moment.").format(_(doc.party_type or "").lower()),
			title=_("Not Accepting Applications"),
		)

	doc.flags.ignore_permissions = True
	doc.submit()
	return get_application(doc.name)


@frappe.whitelist(methods=["POST"])
def attach_uploaded_file() -> ApiResponse[dict]:
	get_current_user()

	content = getattr(frappe.local, "uploaded_file", None)
	filename = getattr(frappe.local, "uploaded_filename", None)
	if content is None or not filename:
		frappe.throw(_("No file was received."), title=_("Upload failed"))

	application = frappe.form_dict.get("application")
	if not application:
		frappe.throw(_("Choose the application this file belongs to."), title=_("Upload failed"))

	file_doc = save_attachment(
		application,
		filename,
		content,
		frappe.form_dict.get("document_type") or None,
		logo=frappe.form_dict.get("purpose") == "logo",
	)
	return ApiResponse.success(
		data={
			"file_url": file_doc["file_url"],
			"file_name": file_doc["file_name"],
			"file_size": file_doc["file_size"],
		}
	)


LOGO_FILE_TYPES = ("png", "jpg", "jpeg", "webp", "gif")


def save_attachment(
	docname: str,
	filename: str,
	content: bytes,
	document_type: str | None = None,
	logo: bool = False,
) -> dict:
	doc = get_own_application(docname, for_write=True)

	if document_type and not any(row.document_type == document_type for row in doc.required_documents):
		frappe.throw(_("{0} is not a document this application asks for.").format(frappe.bold(document_type)))

	validate_upload(filename, content, document_type, LOGO_FILE_TYPES if logo else None)

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"attached_to_doctype": DOCTYPE,
			"attached_to_name": doc.name,
			"is_private": 1,
			"folder": "Home",
		}
	)
	file_doc.save(ignore_permissions=True)

	return file_doc.as_dict()


def validate_upload(
	filename: str,
	content: bytes,
	document_type: str | None = None,
	only: tuple[str, ...] | None = None,
):
	rules = frappe.get_cached_doc("Sourcing Settings").get_upload_rules(document_type)

	extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
	allowed = [ext.lower().lstrip(".") for ext in rules["allowed_file_types"]]
	if only:
		allowed = [ext for ext in allowed if ext in only] or list(only)
	if allowed and extension not in allowed:
		frappe.throw(
			_("{0} files are not accepted here. Allowed: {1}.").format(
				frappe.bold(extension.upper() or _("Untyped")), ", ".join(allowed)
			),
			title=_("File type not allowed"),
		)

	max_size = flt(rules["max_file_size_mb"])
	if max_size and len(content) > max_size * 1024 * 1024:
		frappe.throw(
			_("The file is larger than the {0} MB limit.").format(max_size),
			title=_("File too large"),
		)


@frappe.whitelist()
def get_application_progress(name: str) -> dict:
	get_current_user()

	doc = get_own_application(name)
	always, by_type = doc.get_outstanding_details()

	required_documents = [row for row in doc.required_documents if row.is_mandatory]
	missing_documents = doc.get_outstanding_documents()
	attached = [row for row in required_documents if row.attachment]

	return {
		"missing_details": always + by_type,
		"missing_documents": missing_documents,
		"documents_attached": len(attached),
		"documents_required": len(required_documents),
		"can_submit": not (always or by_type or missing_documents),
	}


def application_status(doc) -> str:
	if doc.docstatus == 0:
		return "Draft"
	return doc.onboarding_status or "Submitted"


def contact_roles(row) -> str:
	flags = ((row.is_primary_contact, _("Primary")), (row.is_billing_contact, _("Billing")))
	roles = [label for flag, label in flags if flag]
	return ", ".join(roles) or _("Other")


def address_use(row) -> str:
	if row.is_primary_address:
		return _("Registered") + (" · " + _("deliveries") if row.is_shipping_address else "")
	return _("Delivery") if row.is_shipping_address else _(row.address_type or "")


APPLICATION_TEMPLATE = "vuna_sourcing/templates/application_summary.html"


def application_html(doc) -> str:
	applicant = [
		("Applying as", _(doc.party_type or "")),
		("Type", doc.onboarding_template),
		("Name", doc.party_name),
		("Tax registration", doc.tax_id),
		("Registration no", doc.registration_number),
		("Country", doc.country),
		("Website", doc.website),
	]
	bank = [
		(label, doc.get(field))
		for label, field in (
			("Bank", "bank"),
			("Account number", "bank_account_no"),
			("Account holder", "account_holder_name"),
			("Branch code", "branch_code"),
			("IBAN", "iban"),
			("SWIFT / BIC", "swift_number"),
		)
	]

	return frappe.get_template(APPLICATION_TEMPLATE).render(
		{
			"doc": doc,
			"status": application_status(doc),
			"company": doc.company,
			"applicant": applicant,
			"bank": bank if any(value for _label, value in bank) else [],
			"roles": contact_roles,
			"address_use": address_use,
		}
	)


@frappe.whitelist()
def download_application(name: str) -> ApiResponse[dict]:
	get_current_user()
	doc = get_own_application(name)

	return ApiResponse.success(
		data={
			"filename": f"{doc.name} - {doc.party_name or _('Application')}.pdf",
			"content": base64.b64encode(get_pdf(application_html(doc))).decode(),
		}
	)
