# Copyright (c) 2026, Vuna Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Abs, IfNull, Sum
from frappe.utils import cint, escape_html, flt, get_link_to_form, now_datetime

from vuna_sourcing.api.transactions.branches import BRANCH_FIELD

DOCTYPE = "Credit Note Request"
SALES_INVOICE = "Sales Invoice"
REQUEST_FIELD = "credit_note_request"
APPROVER_ROLES = ("Accounts Manager",)

PENDING_REVIEW = "Pending Review"
RETURNED = "Returned for Correction"
APPROVED = "Approved"
REJECTED = "Rejected"
ISSUED = "Credit Note Issued"
WITHDRAWN = "Withdrawn"
CANCELLED = "Cancelled"

OPEN_STATUSES = (PENDING_REVIEW, RETURNED, APPROVED)
EDITABLE_AFTER_SUBMIT = (PENDING_REVIEW, RETURNED)


class CreditNoteRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from vuna_sourcing.vuna_sourcing.doctype.credit_note_request_item.credit_note_request_item import (
			CreditNoteRequestItem,
		)

		amended_from: DF.Link | None
		company: DF.Link | None
		credit_note: DF.Link | None
		currency: DF.Link | None
		customer: DF.Link
		customer_name: DF.Data | None
		description: DF.SmallText | None
		items: DF.Table[CreditNoteRequestItem]
		naming_series: DF.Literal["CNR-.YYYY.-"]
		reason: DF.Literal[
			"",
			"Charged More Than Agreed",
			"Agreed Discount Not Applied",
			"Quality Below What Was Ordered",
			"Late Delivery",
			"Other",
		]
		request_status: DF.Literal[
			"",
			"Pending Review",
			"Returned for Correction",
			"Approved",
			"Rejected",
			"Credit Note Issued",
			"Withdrawn",
			"Cancelled",
		]
		requested_by: DF.Link | None
		review_remarks: DF.SmallText | None
		reviewed_by: DF.Link | None
		reviewed_on: DF.Datetime | None
		sales_invoice: DF.Link
		shipping_address_name: DF.Link | None
		total_amount: DF.Currency
		transaction_date: DF.Date | None
	# end: auto-generated types

	def onload(self):
		self.set_onload("draft_credit_note", self.draft_credit_note())
		self.set_onload("can_review", can_review())

	def validate(self):
		self.validate_reason()
		self.refresh_lines()
		self.set_branch()

		if self.docstatus == 0 and self.request_status != RETURNED:
			self.request_status = None

	def set_branch(self):
		self.shipping_address_name = (
			frappe.db.get_value(SALES_INVOICE, self.sales_invoice, BRANCH_FIELD)
			if self.sales_invoice
			else None
		)

	def before_submit(self):
		self.drop_unchanged_lines()
		self.validate_no_open_request()
		self.requested_by = self.requested_by or frappe.session.user
		self.request_status = PENDING_REVIEW
		self.reviewed_by = None
		self.reviewed_on = None
		self.review_remarks = None

	def on_submit(self):
		self.notify_customer(
			_("Credit note request {0} received").format(self.name),
			_(
				"We have received your request {0} to lower prices on invoice {1}. Our accounts team will review it."
			).format(self.name, self.sales_invoice),
		)

	def before_update_after_submit(self):
		if self.request_status not in EDITABLE_AFTER_SUBMIT:
			frappe.throw(
				_("This request is {0}, so it can no longer be changed.").format(_(self.request_status)),
				title=_("Not Allowed"),
			)

		self.validate_reason()
		self.refresh_lines()
		self.drop_unchanged_lines()

	def before_cancel(self):
		credit_notes = frappe.get_all(
			SALES_INVOICE,
			filters={REQUEST_FIELD: self.name, "docstatus": ("<", 2)},
			fields=["name", "docstatus"],
			order_by="creation asc",
		)
		if credit_notes:
			frappe.throw(
				_("This request cannot be cancelled while it has a credit note. Cancel or delete it first:")
				+ "<br>"
				+ "<br>".join(
					"{0} ({1})".format(
						get_link_to_form(SALES_INVOICE, row.name),
						_("Submitted") if row.docstatus == 1 else _("Draft"),
					)
					for row in credit_notes
				),
				title=_("Cannot Cancel"),
			)

	def on_cancel(self):
		if self.flags.withdrawn_by_customer:
			self.db_set("request_status", WITHDRAWN)
			return

		self.db_set("request_status", CANCELLED)
		self.notify_customer(
			_("Credit note request {0} cancelled").format(self.name),
			_(
				"We have cancelled your request {0} to lower prices on invoice {1}. Contact us if you have any questions."
			).format(self.name, self.sales_invoice),
		)

	def validate_reason(self):
		if not self.reason:
			frappe.throw(
				_("Choose why the prices on this invoice should be lowered."), title=_("Reason Needed")
			)

		if self.reason not in reason_options():
			frappe.throw(
				_("{0} is not one of the reasons we accept.").format(self.reason), title=_("Reason Needed")
			)

		if self.reason == "Other" and not (self.description or "").strip():
			frappe.throw(
				_("Describe why the price should be lowered when the reason is Other."),
				title=_("Details Needed"),
			)

	def refresh_lines(self):
		invoice = creditable_invoice(self.sales_invoice, self.customer)
		self.customer = invoice.customer
		self.company = invoice.company
		self.currency = invoice.currency

		lines = {line["sales_invoice_item"]: line for line in invoice_lines(invoice)}
		if not any(line["available_qty"] > 0 for line in lines.values()):
			throw_fully_credited(invoice.name)

		seen = set()
		for row in self.items:
			line = lines.get(row.sales_invoice_item)
			if not line:
				frappe.throw(
					_("Row {0}: {1} is not on invoice {2}.").format(
						row.idx, row.item_name or row.item_code, invoice.name
					)
				)
			if row.sales_invoice_item in seen:
				frappe.throw(
					_("Row {0}: {1} is listed twice. Combine it into one line.").format(
						row.idx, line["item_name"]
					)
				)
			seen.add(row.sales_invoice_item)

			row.update(
				{
					"item_code": line["item_code"],
					"item_name": line["item_name"],
					"uom": line["uom"],
					"rate": line["rate"],
					"qty": line["available_qty"],
				}
			)
			validate_new_rate(row, line, invoice.name)
			row.new_rate = flt(row.new_rate, row.precision("new_rate"))
			reduction = flt(row.rate) - row.new_rate
			row.discount_percentage = (
				flt(reduction / flt(row.rate) * 100, row.precision("discount_percentage")) if row.rate else 0
			)
			row.amount = flt(flt(row.qty) * reduction, row.precision("amount"))

		if not any(is_lowered(row) for row in self.items):
			frappe.throw(_("Lower the price of at least one item."), title=_("Nothing to Adjust"))

		self.total_amount = sum(flt(row.amount) for row in self.items)

	def drop_unchanged_lines(self):
		kept = [row for row in self.items if is_lowered(row)]
		for idx, row in enumerate(kept, start=1):
			row.idx = idx
		self.set("items", kept)

	def validate_no_open_request(self):
		other = open_request_for(self.sales_invoice, exclude=self.name)
		if other:
			frappe.throw(
				_(
					"Credit note request {0} for invoice {1} is still {2}. Wait for it to be decided, or withdraw it, before raising another."
				).format(other.name, self.sales_invoice, _(other.request_status).lower()),
				title=_("Request Already Open"),
			)

	def draft_credit_note(self) -> str | None:
		if self.is_new():
			return None
		return frappe.db.get_value(SALES_INVOICE, {REQUEST_FIELD: self.name, "docstatus": 0}, "name")

	@frappe.whitelist()
	def approve(self, remarks: str | None = None):
		self.check_reviewer()
		self.validate_review_state()

		requested_amount = flt(self.total_amount, self.precision("total_amount"))
		self.refresh_lines()
		if flt(self.total_amount, self.precision("total_amount")) != requested_amount:
			frappe.throw(
				_(
					"Credit notes raised against {0} since this request was made have changed the units it covers. Save the request to refresh its amounts, then approve."
				).format(self.sales_invoice),
				title=_("Invoice Has Changed"),
			)

		self.record_review(APPROVED, remarks)
		self.add_review_comment(_("Approved"), remarks)
		self.notify_customer(
			_("Credit note request {0} approved").format(self.name),
			_(
				"Your request {0} to lower prices on invoice {1} has been approved. We will send the credit note shortly."
			).format(self.name, self.sales_invoice),
		)

	@frappe.whitelist()
	def reject(self, reason: str):
		self.check_reviewer()
		self.validate_review_state()
		require_reason(reason, _("rejecting"))

		self.record_review(REJECTED, reason)
		self.add_review_comment(_("Rejected"), reason)
		self.notify_customer(
			_("Credit note request {0} declined").format(self.name),
			_("Your request {0} to lower prices on invoice {1} was not approved.<br><br>Reason: {2}").format(
				self.name, self.sales_invoice, escape_html(reason)
			),
		)

	@frappe.whitelist()
	def return_for_correction(self, reason: str):
		self.check_reviewer()
		self.validate_review_state()
		require_reason(reason, _("returning it for correction"))

		self.record_review(RETURNED, reason)
		self.add_review_comment(_("Returned for correction"), reason)
		self.notify_customer(
			_("Credit note request {0} needs changes").format(self.name),
			_(
				"Your request {0} to lower prices on invoice {1} needs changes before we can approve it.<br><br>What needs attention: {2}"
			).format(self.name, self.sales_invoice, escape_html(reason)),
		)

	def resubmit(self):
		if self.docstatus != 1 or self.request_status != RETURNED:
			frappe.throw(_("Only a request we sent back for changes can be resubmitted."))

		self.flags.ignore_validate_update_after_submit = True
		self.save()
		self.db_set(
			{
				"request_status": PENDING_REVIEW,
				"reviewed_by": None,
				"reviewed_on": None,
				"review_remarks": None,
			}
		)
		self.add_comment("Comment", _("<b>Resubmitted for review</b>"))

	def check_reviewer(self):
		frappe.only_for(APPROVER_ROLES, message=True)
		self.check_permission("submit")

	def validate_review_state(self):
		if self.docstatus != 1:
			frappe.throw(_("Only a submitted request can be reviewed."))

		if self.request_status != PENDING_REVIEW:
			frappe.throw(
				_("This request is {0} and is no longer awaiting review.").format(
					frappe.bold(self.request_status)
				)
			)

	def record_review(self, status: str, remarks: str | None):
		self.db_set(
			{
				"request_status": status,
				"reviewed_by": frappe.session.user,
				"reviewed_on": now_datetime(),
				"review_remarks": remarks,
			}
		)

	def add_review_comment(self, action: str, remarks: str | None):
		text = f"<b>{action}</b>"
		if remarks:
			text += f"<br>{escape_html(remarks)}"
		self.add_comment("Comment", text)

	def notify_customer(self, subject: str, message: str):
		if not cint(frappe.db.get_single_value("Sourcing Settings", "notify_customer_of_credit_decisions")):
			return

		user = self.requested_by or self.owner
		recipient = frappe.db.get_value("User", {"name": user, "user_type": "Website User"}, "email")
		if not recipient:
			return

		try:
			frappe.sendmail(
				recipients=[recipient],
				subject=subject,
				message=message,
				reference_doctype=self.doctype,
				reference_name=self.name,
			)
		except Exception:
			self.log_error("Credit note request notification failed")


def can_review() -> bool:
	return bool(set(APPROVER_ROLES).intersection(frappe.get_roles()))


def require_reason(reason: str | None, action: str):
	if not (reason or "").strip():
		frappe.throw(_("A reason is required when {0} a request.").format(action))


def reason_options() -> list[str]:
	return [option for option in (frappe.get_meta(DOCTYPE).get_options("reason") or "").split("\n") if option]


def is_lowered(row) -> bool:
	return flt(row.amount) > 0


def creditable_invoice(name: str | None, customer: str | None = None):
	if not name:
		frappe.throw(_("Choose the invoice whose prices you want lowered."))

	invoice = frappe.get_doc(SALES_INVOICE, name)
	if customer and invoice.customer != customer:
		frappe.throw(_("Invoice {0} was not issued to {1}.").format(name, customer))
	if invoice.docstatus != 1:
		frappe.throw(_("Invoice {0} is not submitted, so it cannot be adjusted.").format(name))
	if invoice.is_return:
		frappe.throw(_("{0} is itself a credit note. Choose the original invoice.").format(name))
	if invoice.is_pos and invoice.is_consolidated:
		frappe.throw(_("Invoice {0} combines point-of-sale sales and cannot be adjusted here.").format(name))

	return invoice


def credited_quantities(invoices: list[str], customer: str) -> dict[str, float]:
	if not invoices:
		return {}

	invoice = frappe.qb.DocType(SALES_INVOICE)
	item = frappe.qb.DocType("Sales Invoice Item")
	rows = (
		frappe.qb.from_(item)
		.join(invoice)
		.on(item.parent == invoice.name)
		.select(item.sales_invoice_item, Sum(Abs(item.qty)).as_("qty"))
		.where(invoice.return_against.isin(invoices))
		.where(invoice.customer == customer)
		.where(invoice.docstatus == 1)
		.where(invoice.is_return == 1)
		.where(IfNull(item.sales_invoice_item, "") != "")
		.groupby(item.sales_invoice_item)
	).run(as_dict=True)

	return {row.sales_invoice_item: flt(row.qty) for row in rows}


def invoice_lines(invoice) -> list[dict]:
	credited = credited_quantities([invoice.name], invoice.customer)
	lines = []

	for row in invoice.items:
		credited_qty = credited.get(row.name, 0)
		lines.append(
			{
				"sales_invoice_item": row.name,
				"item_code": row.item_code,
				"item_name": row.item_name or row.item_code,
				"description": row.description,
				"uom": row.uom,
				"rate": row.rate,
				"invoiced_qty": row.qty,
				"credited_qty": credited_qty,
				"available_qty": max(flt(row.qty - credited_qty, row.precision("qty")), 0),
			}
		)

	return lines


def validate_new_rate(row, line: dict, invoice: str):
	new_rate = flt(row.new_rate, row.precision("new_rate"))
	rate = flt(line["rate"])

	if new_rate < 0:
		frappe.throw(
			_("Row {0}: the new price of {1} cannot be below zero.").format(row.idx, line["item_name"]),
			title=_("Invalid Price"),
		)

	if new_rate > rate:
		frappe.throw(
			_("Row {0}: the new price of {1} must be lower than its invoiced price of {2}.").format(
				row.idx, line["item_name"], frappe.format(rate)
			),
			title=_("Invalid Price"),
		)

	if new_rate < rate and line["available_qty"] <= 0:
		frappe.throw(
			_("Row {0}: {1} on invoice {2} is already fully covered by credit notes.").format(
				row.idx, line["item_name"], invoice
			),
			title=_("Already Credited"),
		)


def throw_fully_credited(invoice: str):
	credit_notes = frappe.get_all(
		SALES_INVOICE,
		filters={"return_against": invoice, "is_return": 1, "docstatus": 1},
		pluck="name",
		order_by="posting_date asc",
	)
	frappe.throw(
		_("Invoice {0} has already been fully credited ({1}).").format(invoice, ", ".join(credit_notes)),
		title=_("Already Credited"),
	)


def open_request_for(invoice: str, exclude: str | None = None):
	return frappe.db.get_value(
		DOCTYPE,
		{
			"sales_invoice": invoice,
			"docstatus": 1,
			"request_status": ("in", OPEN_STATUSES),
			"name": ("!=", exclude or ""),
		},
		["name", "request_status"],
		as_dict=True,
	)


@frappe.whitelist()
def get_invoice_lines(sales_invoice: str) -> dict:
	frappe.has_permission(SALES_INVOICE, "read", doc=sales_invoice, throw=True)
	invoice = creditable_invoice(sales_invoice)

	return {
		"customer": invoice.customer,
		"company": invoice.company,
		"currency": invoice.currency,
		"lines": invoice_lines(invoice),
	}


@frappe.whitelist()
def make_credit_note(source_name: str, target_doc: Document | str | None = None) -> Document:
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

	request = frappe.get_doc(DOCTYPE, source_name)
	request.check_permission("read")
	frappe.has_permission(SALES_INVOICE, "create", throw=True)

	if request.docstatus != 1 or request.request_status != APPROVED:
		frappe.throw(_("Only an approved credit note request can be turned into a credit note."))

	draft = request.draft_credit_note()
	if draft:
		frappe.throw(
			_("Draft credit note {0} already exists for this request. Open it instead.").format(
				get_link_to_form(SALES_INVOICE, draft)
			),
			title=_("Credit Note Exists"),
		)

	request.refresh_lines()
	adjusted = {row.sales_invoice_item: row for row in request.items}

	credit_note = make_sales_return(request.sales_invoice, target_doc)
	credit_note.update(
		{
			"update_stock": 0,
			"update_outstanding_for_self": 0,
			"ignore_pricing_rule": 1,
			"additional_discount_percentage": 0,
			"discount_amount": 0,
		}
	)

	lines = []
	for row in credit_note.items:
		adjustment = adjusted.get(row.sales_invoice_item)
		if not adjustment:
			continue
		row.update(
			{
				"qty": -flt(adjustment.qty),
				"stock_qty": -flt(adjustment.qty) * flt(row.conversion_factor or 1),
				"rate": flt(flt(adjustment.rate) - flt(adjustment.new_rate), row.precision("rate")),
				"price_list_rate": 0,
				"discount_percentage": 0,
				"discount_amount": 0,
				"margin_rate_or_amount": 0,
				"pricing_rules": None,
			}
		)
		lines.append(row)

	for idx, row in enumerate(lines, start=1):
		row.idx = idx

	credit_note.set("items", lines)
	credit_note.set(REQUEST_FIELD, request.name)
	credit_note.remarks = _("Credit note request {0}: {1}").format(
		request.name, ". ".join(part for part in (_(request.reason), request.description) if part)
	)
	credit_note.run_method("calculate_taxes_and_totals")
	return credit_note
