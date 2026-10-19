const OPEN_BID_API = "vuna_sourcing.api.transactions.open_bid";

frappe.ui.form.on("Supplier Quotation", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.items.some((row) => row.request_for_quotation)) return;

		if (frm.doc.award_outcome !== "Awarded") {
			frm.remove_custom_button(__("Purchase Order"), __("Create"));
		}

		frappe
			.call({
				method: `${OPEN_BID_API}.get_bid_history`,
				args: { supplier_quotation: frm.doc.name },
			})
			.then(({ message }) => {
				const history = message.data;
				if (!history.bids.length) return;

				frm.add_custom_button(__("Bid History ({0})", [history.bids.length]), () =>
					show_bid_history(history)
				);
			});
	},
});

function show_bid_history(history) {
	const dialog = new frappe.ui.Dialog({
		title: __("Bid History: {0}", [history.supplier]),
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "history" }],
	});
	dialog.fields_dict.history.$wrapper.html(bid_history_html(history));
	dialog.show();
}

function bid_history_html(history) {
	return `
		${bid_summary(history)}
		${bid_report(history.bids)}`;
}

function bid_summary(history) {
	const latest = history.bids[0];
	const first = history.bids[history.bids.length - 1];
	const change = latest.total - first.total;
	const percent = first.total ? Math.abs((change / first.total) * 100).toFixed(1) : null;

	const movement =
		history.bids.length > 1
			? __("From {0} to {1}, {2}", [
					money(first.total, first.currency),
					money(latest.total, latest.currency),
					`<span class="${change_class(change)}">${signed_money(
						change,
						latest.currency
					)}${percent ? ` (${percent}%)` : ""}</span>`,
			  ])
			: __("A single bid of {0}", [money(latest.total, latest.currency)]);

	return `
		<p class="text-muted" style="margin-bottom: var(--margin-md)">
			${__("{0} bids on {1}.", [
				history.bids.length,
				`<a href="/app/request-for-quotation/${encodeURIComponent(
					history.request_for_quotation
				)}">${frappe.utils.escape_html(history.request_for_quotation)}</a>`,
			])}
			${movement}.
		</p>`;
}

function bid_report(bids) {
	const groups = bids.map((bid, index) => revision_rows(bid, index === 0)).join("");

	return `
		<div style="overflow-x: auto">
			<table class="table table-bordered" style="margin-bottom: 0">
				<thead>
					<tr>
						<th>${__("Bid")}</th>
						<th>${__("Placed")}</th>
						<th>${__("Item")}</th>
						<th class="text-right">${__("Qty")}</th>
						<th class="text-right">${__("Rate")}</th>
						<th class="text-right">${__("Amount")}</th>
						<th class="text-right">${__("Lead Time")}</th>
						<th class="text-right">${__("Bid Total")}</th>
						<th class="text-right">${__("Change")}</th>
					</tr>
				</thead>
				${groups}
			</table>
		</div>`;
}

function revision_rows(bid, current) {
	const lines = bid.items.length ? bid.items : [{}];
	const span = `rowspan="${lines.length}" style="vertical-align: top"`;

	const rows = lines.map((line, index) => {
		const revision =
			index === 0
				? `
					<td ${span}>
						<div class="bold">${__("Revision {0}", [bid.revision])}</div>
						${current ? `<span class="indicator-pill green">${__("Current")}</span>` : ""}
					</td>
					<td ${span}>
						<div>${frappe.datetime.str_to_user(bid.placed_at)}</div>
						<div class="text-muted small">${frappe.utils.escape_html(bid.placed_by || "")}</div>
						${
							bid.valid_till
								? `<div class="text-muted small">${__("Valid till {0}", [
										frappe.datetime.str_to_user(bid.valid_till),
								  ])}</div>`
								: ""
						}
					</td>`
				: "";

		const totals =
			index === 0
				? `
					<td ${span} class="text-right bold">${money(bid.total, bid.currency)}</td>
					<td ${span} class="text-right ${change_class(bid.change)}">
						${bid.change === null ? "—" : signed_money(bid.change, bid.currency)}
					</td>`
				: "";

		return `
			<tr>
				${revision}
				<td>${frappe.utils.escape_html(line.item_code || "")}</td>
				<td class="text-right">${line.qty == null ? "—" : format_number(line.qty)}</td>
				<td class="text-right">${line.rate == null ? "—" : money(line.rate, bid.currency)}</td>
				<td class="text-right">${line.amount == null ? "—" : money(line.amount, bid.currency)}</td>
				<td class="text-right">${line.lead_time_days ? __("{0} days", [line.lead_time_days]) : "—"}</td>
				${totals}
			</tr>`;
	});

	return `<tbody style="border-top: 2px solid var(--border-color)">${rows.join("")}</tbody>`;
}

function money(value, currency) {
	return format_currency(value, currency);
}

function signed_money(value, currency) {
	const sign = value > 0 ? "+" : value < 0 ? "−" : "";
	return `${sign}${money(Math.abs(value), currency)}`;
}

function change_class(value) {
	if (!value) return "text-muted";
	return value < 0 ? "text-success" : "text-danger";
}
