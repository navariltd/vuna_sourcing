// Copyright (c) 2026, Vuna Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Party Onboarding Template", {
	setup(frm) {
		vuna_sourcing.set_document_type_query(frm, "required_documents");
	},

	refresh(frm) {
		vuna_sourcing.apply_entity_type_options(frm);
	},

	party_type(frm) {
		vuna_sourcing.apply_entity_type_options(frm);

		const kept = (frm.doc.required_documents || []).length;
		if (kept) {
			frappe.show_alert({
				message: __("Check the required documents still apply to a {0}.", [
					__(frm.doc.party_type).toLowerCase(),
				]),
				indicator: "orange",
			});
		}
	},
});
