// Copyright (c) 2026, Vuna Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sourcing Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Portal Signup Link"), () => show_signup_link(frm));
	},
});

function show_signup_link(frm) {
	frm.call("get_signup_page").then((r) => {
		const data = r.message;
		if (!data) return;

		const dialog = new frappe.ui.Dialog({
			title: __("Portal signup link"),
			fields: [
				{ fieldtype: "HTML", fieldname: "note" },
				{
					fieldtype: "Data",
					fieldname: "url",
					label: __("Link"),
					read_only: 1,
					default: data.url,
				},
			],
			primary_action_label: __("Copy link"),
			primary_action() {
				frappe.utils.copy_to_clipboard(data.url, __("Signup link copied."));
				dialog.hide();
			},
		});

		const as = (data.party_types || []).map((p) => __(p).toLowerCase()).join(__(" or "));
		const note = data.is_open
			? __("Anyone with this link can create an account and apply to become a {0}.", [
					as || __("supplier or customer"),
			  ])
			: __(
					"Registration is set to {0}, so this page will ask the visitor to request an invitation instead of showing a signup form.",
					[__(data.registration_mode)]
			  );

		dialog.fields_dict.note.$wrapper.html(
			`<p class="text-muted" style="margin-bottom: 0.5rem">${note}</p>`
		);

		dialog.show();
	});
}
