// Copyright (c) 2026, Vuna Technologies and contributors
// For license information, please see license.txt

const REVIEWER_ROLES = {
	Supplier: ["Purchase Master Manager"],
	Customer: ["Sales Master Manager"],
};

frappe.ui.form.on("Party Onboarding Request", {
	setup(frm) {
		frm.set_query("onboarding_template", () => ({
			filters: { disabled: 0, party_type: frm.doc.party_type || "" },
		}));
		vuna_sourcing.set_document_type_query(frm, "required_documents");
	},

	onload(frm) {
		vuna_sourcing.apply_entity_type_options(frm);
	},

	refresh(frm) {
		vuna_sourcing.apply_entity_type_options(frm);
		frm.trigger("set_status_indicator");
		frm.trigger("set_review_actions");
		frm.trigger("show_document_checklist");

		if (frm.doc.party) {
			frm.add_custom_button(
				__(frm.doc.party_type),
				() => frappe.set_route("Form", frm.doc.party_type, frm.doc.party),
				__("View")
			);
		}
	},

	party_type(frm) {
		vuna_sourcing.apply_entity_type_options(frm);

		if (frm.doc.onboarding_template) {
			frappe.db
				.get_value("Party Onboarding Template", frm.doc.onboarding_template, "party_type")
				.then(({ message }) => {
					if (message && message.party_type !== frm.doc.party_type) {
						frm.set_value("onboarding_template", null);
					}
				});
		}
	},

	onboarding_template(frm) {
		if (!frm.doc.onboarding_template) {
			frm.clear_table("required_documents");
			frm.refresh_field("required_documents");
			return;
		}

		frappe.db
			.get_doc("Party Onboarding Template", frm.doc.onboarding_template)
			.then((template) => {
				if (!frm.doc.party_type) {
					frm.set_value("party_type", template.party_type);
				}
				frm.trigger("show_document_checklist");
				if (template.description) {
					frappe.show_alert({ message: template.description, indicator: "blue" }, 10);
				}
			});
	},

	set_status_indicator(frm) {
		const colours = {
			"Pending Review": "orange",
			Approved: "green",
			Rejected: "red",
			"Returned for Correction": "yellow",
		};

		if (frm.doc.onboarding_status && !frm.is_new()) {
			frm.page.set_indicator(
				__(frm.doc.onboarding_status),
				colours[frm.doc.onboarding_status] || "gray"
			);
		}
	},

	set_review_actions(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.onboarding_status !== "Pending Review") {
			return;
		}

		const roles = [...(REVIEWER_ROLES[frm.doc.party_type] || []), "Administrator"];
		if (!frappe.user.has_role(roles)) {
			return;
		}

		frm.add_custom_button(__("Approve"), () => confirm_approval(frm)).addClass("btn-primary");
		frm.add_custom_button(__("Return for Correction"), () =>
			prompt_for_reason(
				frm,
				"return_for_correction",
				__("Return for Correction"),
				__("What needs correcting?")
			)
		);
		frm.add_custom_button(__("Reject"), () =>
			prompt_for_reason(frm, "reject", __("Reject Request"), __("Reason for rejection"))
		).addClass("btn-danger");
	},

	show_document_checklist(frm) {
		const outstanding = (frm.doc.required_documents || []).filter(
			(row) => row.is_mandatory && !row.attachment
		);

		frm.dashboard.clear_headline();

		if (!frm.doc.onboarding_template || frm.doc.docstatus !== 0) {
			return;
		}

		if (outstanding.length) {
			frm.dashboard.set_headline(
				__("Still to upload: {0}", [
					outstanding.map((row) => row.document_type).join(", "),
				]),
				"orange"
			);
		} else if ((frm.doc.required_documents || []).length) {
			frm.dashboard.set_headline(__("All required documents are attached."), "green");
		}
	},
});

frappe.ui.form.on("Party Onboarding Request Document", {
	attachment(frm) {
		frm.trigger("show_document_checklist");
	},
	required_documents_remove(frm) {
		frm.trigger("show_document_checklist");
	},
});

frappe.ui.form.on("Party Onboarding Contact", {
	is_primary_contact(frm, cdt, cdn) {
		keep_single(frm, "contacts", "is_primary_contact", cdn);
	},
});

frappe.ui.form.on("Party Onboarding Address", {
	is_primary_address(frm, cdt, cdn) {
		keep_single(frm, "addresses", "is_primary_address", cdn);
	},
});

function keep_single(frm, table, fieldname, cdn) {
	const row = locals[frm.fields_dict[table].grid.doctype][cdn];
	if (!row[fieldname]) return;

	(frm.doc[table] || []).forEach((other) => {
		if (other.name !== cdn && other[fieldname]) {
			frappe.model.set_value(other.doctype, other.name, fieldname, 0);
		}
	});
}

function confirm_approval(frm) {
	const party = __(frm.doc.party_type);
	const dialog = new frappe.ui.Dialog({
		title: __("Approve {0} Onboarding", [party]),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${__(
					"Approving creates the {0}, its contacts, addresses, bank details and document copies.",
					[party]
				)}</p>`,
			},
			{
				fieldname: "remarks",
				fieldtype: "Small Text",
				label: __("Remarks (optional)"),
				default: __("Application passes our requirements"),
			},
		],
		primary_action_label: __("Approve"),
		primary_action(values) {
			dialog.hide();
			frm.call({
				doc: frm.doc,
				method: "approve",
				args: { remarks: values.remarks },
				freeze: true,
				freeze_message: __("Creating {0} records...", [party.toLowerCase()]),
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
