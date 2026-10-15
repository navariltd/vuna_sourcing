const SEALED_BID = "Sealed Bid";
const SEALED_BID_API = "vuna_sourcing.api.transactions.sealed_bid";
const AWARD_API = "vuna_sourcing.api.transactions.award";
const AWARD = "RFQ Award";

const AWARD_OUTCOME_COLORS = { Awarded: "green" };

frappe.ui.form.on("Request for Quotation", {
	setup() {
		show_award_outcome_badges();
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

function show_award_outcome_badges() {
	const supplier = frappe.meta.docfield_map["Request for Quotation Supplier"]?.supplier;
	if (!supplier) return;

	const link = frappe.form.get_formatter("Link");
	supplier.formatter = (value, df, options, row) => {
		const html = link(value, df, options, row);
		const color = AWARD_OUTCOME_COLORS[row?.award_outcome];
		if (!color) return html;
		return `${html} <span class="indicator-pill ${color}">${__(row.award_outcome)}</span>`;
	};
}

function add_award_actions(frm) {
	if (frm.doc.award_status === "Awarded") {
		frm.add_custom_button(__("View Award"), () => open_award(frm));
		return;
	}

	if (frm.doc.award_status !== "Pending Selection") return;

	if (frappe.model.can_create(AWARD)) {
		frm.add_custom_button(__("Award Supplier"), () => start_award(frm), __("Award"));
	}
	if (frappe.model.can_submit(AWARD)) {
		frm.add_custom_button(
			__("Close Without Award"),
			() => close_without_award(frm),
			__("Award")
		);
	}
}

function open_award(frm) {
	frappe.db
		.get_value(AWARD, { request_for_quotation: frm.doc.name, docstatus: 1 }, "name")
		.then(({ message }) => message?.name && frappe.set_route("Form", AWARD, message.name));
}

function start_award(frm) {
	frappe
		.call({ method: `${AWARD_API}.get_award_overview`, args: { name: frm.doc.name } })
		.then(({ message }) => {
			const lowest = message.data.quotes.find((quote) => quote.is_lowest);
			frappe.new_doc(AWARD, {
				request_for_quotation: frm.doc.name,
				supplier_quotation: lowest?.supplier_quotation,
			});
		});
}

function close_without_award(frm) {
	frappe.prompt(
		{
			fieldtype: "Small Text",
			fieldname: "reason",
			label: __("Reason"),
			reqd: 1,
			description: __("Suppliers who quoted are told they were not selected."),
		},
		({ reason }) =>
			frappe
				.call({
					method: `${AWARD_API}.close_without_award`,
					args: { name: frm.doc.name, reason },
					freeze: true,
				})
				.then(({ message }) => {
					frappe.show_alert({ message: message.message, indicator: "orange" });
					frm.reload_doc();
				}),
		__("Close {0} Without Award", [frm.doc.name]),
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
