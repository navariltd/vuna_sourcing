// Copyright (c) 2026, Vuna Technologies and contributors
// For license information, please see license.txt

const AWARD_API = "vuna_sourcing.api.transactions.award";
const KEPT_ON_CANCEL = ["Request for Quotation", "Supplier Quotation"];

frappe.ui.form.on("RFQ Award", {
	setup(frm) {
		frm.ignore_doctypes_on_cancel_all = KEPT_ON_CANCEL;
		frm.set_query("supplier_quotation", () => ({
			filters: {
				name: ["in", (frm.__award_quotes || []).map((quote) => quote.supplier_quotation)],
			},
		}));
	},

	refresh(frm) {
		load_overview(frm);

		if (frm.doc.docstatus === 1 && !frm.doc.__onload?.purchase_orders?.length) {
			frm.add_custom_button(__("Create Purchase Order"), () =>
				create_purchase_order(frm)
			).addClass("btn-primary");
		}
	},

	request_for_quotation(frm) {
		frm.set_value("supplier_quotation", null);
		load_overview(frm);
	},

	supplier_quotation(frm) {
		show_comparison(frm);
	},
});

function load_overview(frm) {
	if (!frm.doc.request_for_quotation) {
		frm.__award_quotes = [];
		frm.get_field("comparison").$wrapper.empty();
		return;
	}

	frappe
		.call({
			method: `${AWARD_API}.get_award_overview`,
			args: { name: frm.doc.request_for_quotation },
		})
		.then(({ message }) => {
			frm.__award_quotes = message.data.quotes;
			frm.__award_blockers = message.data.blockers;
			show_comparison(frm);
		});
}

function show_comparison(frm) {
	const quotes = frm.__award_quotes || [];
	const wrapper = frm.get_field("comparison").$wrapper;

	if (frm.doc.docstatus === 0 && frm.__award_blockers?.length) {
		wrapper.html(
			`<div class="alert alert-warning">${frm.__award_blockers
				.map((blocker) => frappe.utils.escape_html(blocker))
				.join("<br>")}</div>`
		);
		return;
	}

	if (!quotes.length) {
		wrapper.html(`<p class="text-muted">${__("No submitted quotations yet.")}</p>`);
		return;
	}

	const rows = quotes
		.map((quote) => {
			const chosen = quote.supplier_quotation === frm.doc.supplier_quotation;
			const pick =
				frm.doc.docstatus === 0 && !chosen
					? `<button class="btn btn-xs btn-default" data-quote="${frappe.utils.escape_html(
							quote.supplier_quotation
					  )}">${__("Select")}</button>`
					: chosen
					? `<span class="indicator-pill green">${__("Selected")}</span>`
					: "";
			return `
				<tr>
					<td>${quote.rank}</td>
					<td>
						<a href="${frappe.utils.get_form_link("Supplier Quotation", quote.supplier_quotation)}">
							${frappe.utils.escape_html(quote.supplier_name || quote.supplier)}
						</a>
						${quote.is_lowest ? `<span class="indicator-pill blue">${__("Lowest")}</span>` : ""}
					</td>
					<td class="text-right">${format_currency(quote.total, quote.currency)}</td>
					<td class="text-right">${format_currency(quote.base_total)}</td>
					<td class="text-right">${pick}</td>
				</tr>`;
		})
		.join("");

	wrapper.html(`
		<table class="table table-bordered" style="margin-bottom: 0">
			<thead>
				<tr>
					<th style="width: 60px">${__("Rank")}</th>
					<th>${__("Supplier")}</th>
					<th class="text-right">${__("Total")}</th>
					<th class="text-right">${__("Total (Company Currency)")}</th>
					<th style="width: 100px"></th>
				</tr>
			</thead>
			<tbody>${rows}</tbody>
		</table>`);

	wrapper.find("button[data-quote]").on("click", (event) => {
		frm.set_value("supplier_quotation", $(event.currentTarget).attr("data-quote"));
	});
}

function create_purchase_order(frm) {
	frm.call({ method: "create_purchase_order", doc: frm.doc, freeze: true }).then(
		({ message }) => {
			frappe.show_alert({ message: message.message, indicator: "green" });
			frappe.set_route("Form", "Purchase Order", message.data.purchase_order);
		}
	);
}
