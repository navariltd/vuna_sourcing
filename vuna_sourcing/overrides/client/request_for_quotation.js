const SEALED_BID = "Sealed Bid";
const SEALED_BID_API = "vuna_sourcing.api.transactions.sealed_bid";

frappe.ui.form.on("Request for Quotation", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.bidding_method !== SEALED_BID) return;

		frappe
			.call({ method: `${SEALED_BID_API}.get_opening_status`, args: { name: frm.doc.name } })
			.then(({ message }) => show_opening_status(frm, message.data));
	},
});

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
