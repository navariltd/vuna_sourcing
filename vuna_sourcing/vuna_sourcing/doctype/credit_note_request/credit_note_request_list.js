// Copyright (c) 2026, Vuna Technologies and contributors
// For license information, please see license.txt

frappe.listview_settings["Credit Note Request"] = {
	add_fields: ["request_status"],
	get_indicator(doc) {
		const colours = {
			"Pending Review": "orange",
			"Returned for Correction": "yellow",
			Approved: "blue",
			Rejected: "red",
			"Credit Note Issued": "green",
			Withdrawn: "gray",
			Cancelled: "red",
		};
		const status = doc.request_status || "Pending Review";
		return [__(status), colours[status] || "gray", `request_status,=,${status}`];
	},
};
