const SEALED_BID = "Sealed Bid";
const SEALED_BID_API = "vuna_sourcing.api.transactions.sealed_bid";
const AWARD_API = "vuna_sourcing.api.transactions.award";
const AWARD = "Request for Quotation Award";
const AWARDED = "Awarded";

frappe.ui.form.on("Request for Quotation", {
	setup() {
		show_awarded_badge("Request for Quotation Supplier", "supplier", "award_outcome");
		show_awarded_badge("Request for Quotation Item", "item_code", "award_status");
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		add_award_actions(frm);

		if (frm.doc.bidding_method !== SEALED_BID) return;

		frappe
			.call({ method: `${SEALED_BID_API}.get_opening_status`, args: { name: frm.doc.name } })
			.then(({ message }) => show_opening_status(frm, message.data));
	},
});

function show_awarded_badge(doctype, fieldname, status_field) {
	const field = frappe.meta.docfield_map[doctype]?.[fieldname];
	if (!field) return;

	const link = frappe.form.get_formatter("Link");
	field.formatter = (value, df, options, row) => {
		const html = link(value, df, options, row);
		if (row?.[status_field] !== AWARDED) return html;
		return `${html} <span class="indicator-pill green">${__(AWARDED)}</span>`;
	};
}

function add_award_actions(frm) {
	const status = frm.doc.award_status;
	const open = ["Pending Selection", "Partially Awarded"].includes(status);

	if (open && frappe.model.can_create(AWARD)) {
		frm.add_custom_button(__("Award Supplier"), () => start_award(frm), __("Award"));
	}
	if (open && frappe.model.can_submit(AWARD)) {
		const label =
			status === "Partially Awarded"
				? __("Close Remaining Items")
				: __("Close Without Award");
		frm.add_custom_button(label, () => close_remaining_items(frm, label), __("Award"));
	}
	if (["Partially Awarded", "Awarded"].includes(status)) {
		frm.add_custom_button(
			__("View Awards"),
			() => frappe.set_route("List", AWARD, { request_for_quotation: frm.doc.name }),
			__("Award")
		);
	}
}

function start_award(frm) {
	frappe
		.call({ method: `${AWARD_API}.get_award_overview`, args: { name: frm.doc.name } })
		.then(({ message }) => {
			const today = frappe.datetime.get_today();
			const lowest = message.data.quotes.find(
				(quote) => !quote.valid_till || quote.valid_till >= today
			);
			frappe.new_doc(AWARD, {
				request_for_quotation: frm.doc.name,
				award_basis: lowest ? "Full Award" : "Partial Award",
				awarded_quotation: lowest?.supplier_quotation,
			});
		});
}

function close_remaining_items(frm, label) {
	frappe.prompt(
		{
			fieldtype: "Small Text",
			fieldname: "reason",
			label: __("Reason"),
			reqd: 1,
			description: __(
				"Items not yet awarded are closed. Suppliers who won nothing are told they were not selected."
			),
		},
		({ reason }) =>
			frappe
				.call({
					method: `${AWARD_API}.close_remaining_items`,
					args: { name: frm.doc.name, reason },
					freeze: true,
				})
				.then(({ message }) => {
					frappe.show_alert({ message: message.message, indicator: "orange" });
					frm.reload_doc();
				}),
		label,
		__("Close")
	);
}

function show_opening_status(frm, status) {
	frm.get_field("opening_conditions").$wrapper.html(opening_conditions(status));

	if (status.can_confirm) {
		frm.add_custom_button(__("Open Quotes"), () => confirm_opening(frm, status)).addClass(
			"btn-primary"
		);
	}
}

function opening_conditions(status) {
	const rows = status.conditions
		.map(
			(condition) => `
				<tr>
					<td style="width: 130px">${condition_pill(condition)}</td>
					<td class="bold">${frappe.utils.escape_html(condition.label)}</td>
					<td class="text-muted">${frappe.utils.escape_html(condition_detail(condition))}</td>
				</tr>`
		)
		.join("");

	const outcome = status.opened
		? `<span class="indicator-pill green">${__("Quotations are open")}</span>`
		: `<span class="indicator-pill orange">${__(
				"Quotations stay sealed until every required condition is met"
		  )}</span>`;

	return `
		<div class="mb-3">${outcome}</div>
		<table class="table table-bordered" style="margin-bottom: 0">${rows}</table>`;
}

function condition_detail(condition) {
	if (!condition.at) return condition.detail;
	return `${condition.prefix} ${frappe.datetime.str_to_user(condition.at)}`;
}

function condition_pill(condition) {
	if (!condition.required) {
		return `<span class="indicator-pill blue">${__("Not required")}</span>`;
	}

	return condition.met
		? `<span class="indicator-pill green">${__("Met")}</span>`
		: `<span class="indicator-pill gray">${__("Waiting")}</span>`;
}

function confirm_opening(frm, status) {
	frappe.confirm(
		__("Confirm that you are opening the sealed quotations for {0}? Committee: {1}.", [
			frm.doc.name,
			committee_progress(status),
		]),
		() =>
			frappe
				.call({
					method: `${SEALED_BID_API}.open_quotes`,
					args: { name: frm.doc.name },
					freeze: true,
				})
				.then(({ message }) => {
					frappe.show_alert({ message: message.message, indicator: "green" });
					frm.reload_doc();
				})
	);
}

function committee_progress(status) {
	const committee = status.conditions.find(
		(condition) => condition.key === "committee_confirmed"
	);
	return frappe.utils.escape_html(committee.detail);
}
