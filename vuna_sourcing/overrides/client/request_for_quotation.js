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
	const closing = frappe.datetime.str_to_user(status.closes_at);
	const conditions = [
		{
			label: __("Bids closed"),
			met: status.closed,
			detail: status.closed
				? __("Closed at {0}", [closing])
				: __("Closes at {0}", [closing]),
		},
		{
			label: __("Minimum quotations received"),
			met: status.received >= status.expected,
			detail: __("{0} received, {1} required", [status.received, status.expected]),
		},
		{
			label: __("Every committee member confirmed"),
			met: status.confirmations === status.members,
			detail: status.waiting.length
				? __("{0} of {1} confirmed. Waiting for {2}", [
						status.confirmations,
						status.members,
						status.waiting.join(", "),
				  ])
				: __("{0} of {1} confirmed", [status.confirmations, status.members]),
		},
	];

	const rows = conditions
		.map(
			(condition) => `
				<tr>
					<td style="width: 110px">
						<span class="indicator-pill ${condition.met ? "green" : "gray"}">
							${condition.met ? __("Met") : __("Waiting")}
						</span>
					</td>
					<td class="bold">${condition.label}</td>
					<td class="text-muted">${frappe.utils.escape_html(condition.detail)}</td>
				</tr>`
		)
		.join("");

	const outcome = status.opened
		? `<span class="indicator-pill green">${__("Quotations are open")}</span>`
		: `<span class="indicator-pill orange">${__(
				"Quotations stay sealed until every condition is met"
		  )}</span>`;

	return `
		<div class="mb-3">${outcome}</div>
		<table class="table table-bordered" style="margin-bottom: 0">${rows}</table>`;
}

function confirm_opening(frm, status) {
	frappe.confirm(
		__(
			"Confirm that you are opening the sealed quotations for {0}? They open once all {1} committee members confirm; {2} have so far.",
			[frm.doc.name, status.members, status.confirmations]
		),
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
