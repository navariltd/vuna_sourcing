// Copyright (c) 2026, Vuna Technologies and contributors
// For license information, please see license.txt

const CREDIT_REQUEST_MODULE =
	"vuna_sourcing.vuna_sourcing.doctype.credit_note_request.credit_note_request";

const STATUS_COLOURS = {
	"Pending Review": "orange",
	"Returned for Correction": "yellow",
	Approved: "blue",
	Rejected: "red",
	"Credit Note Issued": "green",
	Withdrawn: "gray",
	Cancelled: "red",
};

frappe.ui.form.on("Credit Note Request", {
	setup(frm) {
		frm.set_query("sales_invoice", () => ({
			filters: {
				docstatus: 1,
				is_return: 0,
				...(frm.doc.customer ? { customer: frm.doc.customer } : {}),
			},
		}));
		frm.set_df_property("items", "cannot_add_rows", true);
	},

	refresh(frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("set_editable");
		frm.trigger("show_next_step");
		frm.trigger("set_review_actions");
		frm.trigger("set_credit_note_actions");

		if (frm.doc.sales_invoice) {
			frm.add_custom_button(
				__("Sales Invoice"),
				() => frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice),
				__("View")
			);
		}
	},

	customer(frm) {
		if (!frm.doc.sales_invoice || !frm.doc.customer) return;

		frappe.db
			.get_value("Sales Invoice", frm.doc.sales_invoice, "customer")
			.then(({ message }) => {
				if (message && message.customer !== frm.doc.customer) {
					frm.set_value("sales_invoice", null);
				}
			});
	},

	sales_invoice(frm) {
		frm.clear_table("items");
		frm.refresh_field("items");
		update_totals(frm);

		if (!frm.doc.sales_invoice) return;

		frappe
			.xcall(`${CREDIT_REQUEST_MODULE}.get_invoice_lines`, {
				sales_invoice: frm.doc.sales_invoice,
			})
			.then((invoice) => {
				const open_lines = invoice.lines.filter((line) => line.available_qty > 0);
				if (!open_lines.length) {
					frappe.msgprint({
						title: __("Already Credited"),
						message: __("Invoice {0} has already been fully credited.", [
							frm.doc.sales_invoice,
						]),
						indicator: "orange",
					});
					frm.set_value("sales_invoice", null);
					return;
				}

				frm.set_value({
					customer: invoice.customer,
					company: invoice.company,
					currency: invoice.currency,
				});

				open_lines.forEach((line) => {
					frm.add_child("items", {
						sales_invoice_item: line.sales_invoice_item,
						item_code: line.item_code,
						item_name: line.item_name,
						uom: line.uom,
						rate: line.rate,
						invoiced_qty: line.invoiced_qty,
						credited_qty: line.credited_qty,
						qty: 0,
						amount: 0,
					});
				});
				frm.refresh_field("items");
				frappe.show_alert({
					message: __(
						"Enter the quantity to credit on each line. Lines left at 0 are dropped."
					),
					indicator: "blue",
				});
			});
	},

	set_status_indicator(frm) {
		if (frm.is_new() || !frm.doc.request_status) return;

		frm.page.set_indicator(
			__(frm.doc.request_status),
			STATUS_COLOURS[frm.doc.request_status] || "gray"
		);
	},

	set_editable(frm) {
		const reviewing =
			frm.doc.docstatus === 1 &&
			frm.doc.request_status === "Pending Review" &&
			frm.doc.__onload?.can_review;
		const editable = frm.doc.docstatus === 0 || reviewing;

		frm.set_df_property("items", "read_only", editable ? 0 : 1);
		frm.toggle_enable(["reason", "description"], editable);
	},

	show_next_step(frm) {
		frm.dashboard.clear_headline();
		if (frm.doc.docstatus !== 1) return;

		const draft = frm.doc.__onload?.draft_credit_note;
		const steps = {
			"Pending Review": frm.doc.__onload?.can_review
				? [
						__(
							"Check the quantities, then approve, send back or reject. You can lower a quantity and save before approving."
						),
						"orange",
				  ]
				: [__("Waiting for an Accounts Manager to review this request."), "orange"],
			"Returned for Correction": [
				__("Sent back to the customer for changes. It returns here when they resubmit."),
				"yellow",
			],
			Approved: draft
				? [__("Draft credit note {0} is waiting to be submitted.", [draft]), "blue"]
				: [__("Approved. Create the credit note to finish."), "blue"],
			"Credit Note Issued": [__("Credited by {0}.", [frm.doc.credit_note]), "green"],
		};

		const step = steps[frm.doc.request_status];
		if (step) frm.dashboard.set_headline(step[0], step[1]);
	},

	set_review_actions(frm) {
		if (
			frm.doc.docstatus !== 1 ||
			frm.doc.request_status !== "Pending Review" ||
			!frm.doc.__onload?.can_review
		) {
			return;
		}

		frm.add_custom_button(__("Approve"), () => confirm_approval(frm)).addClass("btn-primary");
		frm.add_custom_button(__("Return for Correction"), () =>
			prompt_for_reason(
				frm,
				"return_for_correction",
				__("Return for Correction"),
				__("What should the customer change?")
			)
		);
		frm.add_custom_button(__("Reject"), () =>
			prompt_for_reason(frm, "reject", __("Reject Request"), __("Reason for rejection"))
		).addClass("btn-danger");
	},

	set_credit_note_actions(frm) {
		if (frm.doc.docstatus !== 1) return;

		if (frm.doc.credit_note) {
			frm.add_custom_button(
				__("Credit Note"),
				() => frappe.set_route("Form", "Sales Invoice", frm.doc.credit_note),
				__("View")
			);
			return;
		}

		if (frm.doc.request_status !== "Approved") return;

		const draft = frm.doc.__onload?.draft_credit_note;
		if (draft) {
			frm.add_custom_button(__("Open Draft Credit Note"), () =>
				frappe.set_route("Form", "Sales Invoice", draft)
			).addClass("btn-primary");
			return;
		}

		frm.add_custom_button(__("Create Credit Note"), () =>
			frappe.model.open_mapped_doc({
				method: `${CREDIT_REQUEST_MODULE}.make_credit_note`,
				frm: frm,
			})
		).addClass("btn-primary");
	},
});

frappe.ui.form.on("Credit Note Request Item", {
	qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
		update_totals(frm);
	},
});

function update_totals(frm) {
	const items = frm.doc.items || [];
	frm.set_value(
		"total_qty",
		items.reduce((total, row) => total + flt(row.qty), 0)
	);
	frm.set_value(
		"total_amount",
		items.reduce((total, row) => total + flt(row.qty) * flt(row.rate), 0)
	);
}

function confirm_approval(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save your changes to the quantities before approving."));
		return;
	}

	const amount = format_currency(frm.doc.total_amount, frm.doc.currency);
	const dialog = new frappe.ui.Dialog({
		title: __("Approve Credit Note Request"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${__(
					"Approving agrees to credit {0} (before taxes) against {1}. You then create the credit note from this request.",
					[amount, frm.doc.sales_invoice]
				)}</p>`,
			},
			{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks (optional)") },
		],
		primary_action_label: __("Approve"),
		primary_action(values) {
			dialog.hide();
			frm.call({
				doc: frm.doc,
				method: "approve",
				args: { remarks: values.remarks },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		},
	});
	dialog.show();
}

function prompt_for_reason(frm, method, title, label) {
	const dialog = new frappe.ui.Dialog({
		title: title,
		fields: [{ fieldname: "reason", fieldtype: "Small Text", label: label, reqd: 1 }],
		primary_action_label: title,
		primary_action(values) {
			dialog.hide();
			frm.call({
				doc: frm.doc,
				method: method,
				args: { reason: values.reason },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		},
	});
	dialog.show();
}
