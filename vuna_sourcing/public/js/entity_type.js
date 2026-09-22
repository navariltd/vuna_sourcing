// Copyright (c) 2026, Vuna Technologies and contributors
// For license information, please see license.txt

frappe.provide("vuna_sourcing");

vuna_sourcing.ENTITY_FIELD = { Supplier: "supplier_type", Customer: "customer_type" };

vuna_sourcing.apply_entity_type_options = function (frm, fieldname = "entity_type") {
	const party_type = frm.doc.party_type;
	if (!frm.fields_dict[fieldname] || !party_type) {
		return;
	}

	frappe.model.with_doctype(party_type, () => {
		const df = frappe.meta.get_docfield(party_type, vuna_sourcing.ENTITY_FIELD[party_type]);
		frm.set_df_property(fieldname, "options", df ? df.options : "");
		frm.refresh_field(fieldname);
	});
};

vuna_sourcing.set_document_type_query = function (frm, table) {
	frm.set_query("document_type", table, () => ({
		filters: {
			disabled: 0,
			applies_to: ["in", ["Supplier and Customer", frm.doc.party_type || ""]],
		},
	}));
};
