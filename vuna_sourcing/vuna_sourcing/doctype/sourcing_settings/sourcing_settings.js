// Copyright (c) 2026, Vuna Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sourcing Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Portal Signup Link"), () => show_signup_link(frm));
		frm.add_custom_button(__("Invite User"), () => show_invite_user());
	},
});

function show_invite_user() {
	frappe
		.call({ method: "vuna_sourcing.api.signup.get_signup_context" })
		.then(({ message: context }) => {
			const branding = context?.data || {};

			const dialog = new frappe.ui.Dialog({
				title: __("Invite User"),
				fields: [
					{ fieldtype: "HTML", fieldname: "intro" },
					{ fieldtype: "Section Break" },
					{
						fieldtype: "Data",
						fieldname: "first_name",
						label: __("First Name"),
						reqd: 1,
					},
					{ fieldtype: "Column Break" },
					{
						fieldtype: "Data",
						fieldname: "last_name",
						label: __("Last Name"),
						reqd: 1,
					},
					{ fieldtype: "Section Break" },
					{
						fieldtype: "Data",
						fieldname: "email",
						label: __("Email"),
						options: "Email",
						reqd: 1,
					},
				],
				primary_action_label: __("Send Invitation"),
				primary_action(values) {
					dialog.disable_primary_action();
					frappe
						.call({
							method: "vuna_sourcing.api.signup.sign_up",
							type: "POST",
							args: values,
						})
						.then(({ message: response }) => {
							if (!response?.ok) {
								frappe.msgprint({
									title: __("Invitation not sent"),
									message: response?.message,
									indicator: "orange",
								});
								return;
							}

							dialog.hide();
							if (response.data.email_sent) {
								frappe.show_alert({
									message: __("Invitation sent to {0}.", [response.data.email]),
									indicator: "green",
								});
							} else {
								frappe.msgprint({
									title: __("Account created"),
									message: __(
										"The account for {0} was created, but the invitation email could not be sent. Check the outgoing email account and resend the welcome email from the user record.",
										[response.data.email]
									),
									indicator: "orange",
								});
							}
						})
						.always(() => dialog.enable_primary_action());
				},
			});

			const title = frappe.utils.escape_html(branding.app_title || __("Sourcing Portal"));
			dialog.fields_dict.intro.$wrapper.html(
				`<p class="text-muted" style="margin-bottom: 0.5rem">${__(
					"They get an email to set a password for {0}, then they can apply to become a supplier or customer. To add someone to an existing customer, use the Portal Users table on that customer.",
					[title]
				)}</p>`
			);

			dialog.show();
		});
}

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

		const as = (data.party_types || []).map((p) => __(p).toLowerCase()).join(` ${__("or")} `);
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
