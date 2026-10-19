// Copyright (c) 2026, Vuna Technologies and contributors
// For license information, please see license.txt

const AWARD_API = "vuna_sourcing.api.transactions.award";
const FULL_AWARD = "Full Award";
const QUOTES_SHOWN = 5;
const ITEM_TOOLS_FROM = 8;
const PICKER_ROWS = 100;
const BID_FIELDS = [
	"supplier_quotation",
	"supplier_quotation_item",
	"supplier",
	"currency",
	"rate",
	"amount",
	"base_rate",
	"base_amount",
	"item_rank",
	"is_lowest",
];

const STYLE = `
	.rfqa { display: flex; flex-direction: column; gap: 12px; }
	.rfqa-summary { display: flex; flex-wrap: wrap; gap: 8px 24px; padding: 12px 16px; border: 1px solid var(--border-color); border-radius: 10px; background: var(--subtle-fg); }
	.rfqa-stat { display: flex; flex-direction: column; min-width: 110px; }
	.rfqa-stat-label { font-size: var(--text-xs); color: var(--text-muted); }
	.rfqa-stat-value { font-size: var(--text-md); font-weight: 600; color: var(--text-color); }
	.rfqa-stat-note { font-size: var(--text-xs); color: var(--text-muted); }
	.rfqa-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
	.rfqa-toolbar .rfqa-search { flex: 1 1 220px; max-width: 320px; }
	.rfqa-spacer { flex: 1; }
	.rfqa-tabs { display: inline-flex; border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; }
	.rfqa-tab { padding: 4px 10px; font-size: var(--text-sm); color: var(--text-muted); background: var(--fg-color); border: 0; cursor: pointer; }
	.rfqa-tab + .rfqa-tab { border-left: 1px solid var(--border-color); }
	.rfqa-tab.active { background: var(--subtle-accent); color: var(--text-color); font-weight: 600; }
	.rfqa-list { border: 1px solid var(--border-color); border-radius: 10px; overflow: hidden; }
	.rfqa-list.scroll { max-height: 520px; overflow-y: auto; }
	.rfqa-row { display: grid; grid-template-columns: minmax(200px, 260px) 1fr; gap: 16px; padding: 12px 16px; align-items: start; background: var(--fg-color); }
	.rfqa-row + .rfqa-row { border-top: 1px solid var(--border-color); }
	.rfqa-row.open { background: var(--subtle-fg); }
	.rfqa-item-name { font-weight: 600; color: var(--text-color); }
	.rfqa-muted { font-size: var(--text-xs); color: var(--text-muted); }
	.rfqa-bids { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
	.rfqa-bid { display: flex; flex-direction: column; align-items: flex-start; min-width: 0; width: 100%; padding: 6px 10px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--fg-color); color: var(--text-color); text-align: left; cursor: pointer; line-height: 1.3; }
	.rfqa-bid:hover { border-color: var(--gray-400); background: var(--fg-hover-color); }
	.rfqa-bid[disabled] { cursor: default; }
	.rfqa-bid-supplier { font-size: var(--text-xs); color: var(--text-muted); max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.rfqa-bid-price { font-weight: 600; font-size: var(--text-sm); }
	.rfqa-bid.selected { border-color: var(--green-500); background: var(--bg-green); }
	.rfqa-bid.selected .rfqa-bid-supplier, .rfqa-bid.selected .rfqa-bid-price { color: var(--text-on-green); }
	.rfqa-tag { display: inline-block; margin-left: 4px; padding: 0 6px; border-radius: 6px; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .02em; }
	.rfqa-tag.lowest { background: var(--bg-blue); color: var(--text-on-blue); }
	.rfqa-tag.above { background: var(--bg-orange); color: var(--text-on-orange); }
	.rfqa-tag.expired { background: var(--bg-gray); color: var(--text-muted); }
	.rfqa-bid.expired { opacity: .55; cursor: not-allowed; }
	.rfqa-bid.expired:hover { border-color: var(--border-color); background: var(--fg-color); }
	.rfqa-justify textarea.rfqa-missing { border: 1px solid var(--red-500); box-shadow: 0 0 0 2px var(--red-100); }
	.rfqa-more { padding: 6px 10px; border: 1px dashed var(--border-color); border-radius: 8px; background: transparent; color: var(--text-muted); font-size: var(--text-sm); cursor: pointer; min-height: 44px; }
	.rfqa-status { margin-top: 6px; font-size: var(--text-xs); }
	.rfqa-status.good { color: var(--green-600); }
	.rfqa-status.warn { color: var(--orange-600, #c2410c); }
	.rfqa-justify { grid-column: 2; }
	.rfqa-justify textarea.form-control { height: 56px; min-height: 56px; resize: vertical; font-size: var(--text-sm); }
	.rfqa-more:hover { color: var(--text-color); border-color: var(--gray-400); }
	.rfqa-link { border: 0; background: none; padding: 0; color: var(--text-muted); font-size: var(--text-xs); text-decoration: underline; cursor: pointer; }
	.rfqa-quote { display: grid; grid-template-columns: 44px minmax(160px, 2fr) minmax(120px, 1fr) minmax(110px, auto) 110px; gap: 12px; padding: 10px 16px; align-items: center; background: var(--fg-color); }
	.rfqa-quote + .rfqa-quote { border-top: 1px solid var(--border-color); }
	.rfqa-quote.selected { background: var(--bg-green); }
	.rfqa-rank { width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; font-weight: 600; background: var(--subtle-accent); color: var(--text-color); }
	.rfqa-quote.selected .rfqa-rank { background: var(--green-500); color: #fff; }
	.rfqa-right { text-align: right; }
	.rfqa-empty { padding: 16px; color: var(--text-muted); text-align: center; }
	@media (max-width: 767px) {
		.rfqa-row { grid-template-columns: 1fr; }
		.rfqa-bids { grid-template-columns: repeat(2, minmax(0, 1fr)); }
		.rfqa-justify { grid-column: 1; }
		.rfqa-quote { grid-template-columns: 36px 1fr auto; }
		.rfqa-quote .rfqa-hide-sm { display: none; }
	}
`;

frappe.ui.form.on("Request for Quotation Award", {
	setup(frm) {
		frm.set_query("awarded_quotation", () => ({
			query: `${AWARD_API}.quotation_query`,
			filters: {
				request_for_quotation: frm.doc.request_for_quotation,
				award: frm.doc.docstatus === 1 ? frm.doc.name : null,
			},
		}));
		frm.set_query("supplier_quotation", "items", (doc, cdt, cdn) => ({
			query: `${AWARD_API}.quotation_query`,
			filters: {
				request_for_quotation: frm.doc.request_for_quotation,
				request_for_quotation_item: locals[cdt][cdn].request_for_quotation_item,
			},
		}));
	},

	refresh(frm) {
		frm.__view = frm.__view || { search: "", filter: "all", show_all_quotes: false };
		set_items_editable(frm);
		load_overview(frm);
	},

	request_for_quotation(frm) {
		frm.set_value("awarded_quotation", null);
		frm.clear_table("items");
		frm.refresh_field("items");
		load_overview(frm);
	},

	award_basis(frm) {
		frm.__view = { search: "", filter: "all", show_all_quotes: false };
		set_items_editable(frm);
		if (frm.doc.award_basis === FULL_AWARD) {
			const lowest = quotes(frm).find((quote) => !is_expired(frm, quote));
			if (!frm.doc.awarded_quotation && lowest) {
				frm.set_value("awarded_quotation", lowest.supplier_quotation);
				return;
			}
			fill_from_quotation(frm);
		} else {
			fill_best_bids(frm);
		}
	},

	awarded_quotation(frm) {
		const quote = quotes(frm).find(
			(candidate) => candidate.supplier_quotation === frm.doc.awarded_quotation
		);
		frm.doc.supplier = quote?.supplier || null;
		frm.doc.supplier_name = quote?.supplier_name || null;
		frm.doc.rank = quote?.rank || 0;
		frm.doc.is_lowest = quote?.is_lowest ? 1 : 0;
		frm.refresh_fields(["supplier", "supplier_name", "rank", "is_lowest", "justification"]);
		if (frm.doc.award_basis === FULL_AWARD) fill_from_quotation(frm);
	},

	award_date(frm) {
		render(frm);
	},

	items_remove(frm) {
		render(frm);
	},

	validate(frm) {
		const problems = client_problems(frm);
		if (!problems.length) return;
		frappe.validated = false;
		frappe.msgprint({
			title: __("Before you save"),
			message: `<ul style="padding-left: 1.2em; margin: 0">${problems
				.map((problem) => `<li>${problem}</li>`)
				.join("")}</ul>`,
			indicator: "orange",
		});
		point_at_missing_justification(frm);
	},
});

frappe.ui.form.on("Request for Quotation Award Item", {
	supplier_quotation(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.supplier_quotation) return;
		item_bids(frm, row.request_for_quotation_item).then((bids) => {
			const bid = bids.find(
				(candidate) => candidate.supplier_quotation === row.supplier_quotation
			);
			if (bid) apply_bid(row, bid);
			frm.refresh_field("items");
			render(frm);
		});
	},
});

function load_overview(frm) {
	frm.__bids = {};
	if (!frm.doc.request_for_quotation) {
		frm.__overview = null;
		render(frm);
		return;
	}

	frappe
		.call({
			method: `${AWARD_API}.get_award_overview`,
			args: {
				name: frm.doc.request_for_quotation,
				award: frm.doc.docstatus === 1 ? frm.doc.name : null,
			},
		})
		.then(({ message }) => {
			frm.__overview = message.data;
			if (frm.doc.docstatus === 0 && !(frm.doc.items || []).length) {
				if (frm.doc.award_basis === FULL_AWARD) {
					fill_from_quotation(frm);
				} else {
					fill_best_bids(frm);
				}
			}
			render(frm);
		});
}

function quotes(frm) {
	return frm.__overview?.quotes || [];
}

function lines(frm) {
	return frm.__overview?.lines || [];
}

function company_currency(frm) {
	return (
		(frm.doc.company && erpnext?.get_currency?.(frm.doc.company)) ||
		frappe.boot.sysdefaults.currency
	);
}

function item_bids(frm, rfq_item) {
	if (frm.__bids[rfq_item]) return Promise.resolve(frm.__bids[rfq_item]);
	return frappe
		.call({
			method: `${AWARD_API}.get_item_bids`,
			args: { name: frm.doc.request_for_quotation, request_for_quotation_item: rfq_item },
		})
		.then(({ message }) => (frm.__bids[rfq_item] = message.data));
}

function set_items_editable(frm) {
	const editable = frm.doc.docstatus === 0 && frm.doc.award_basis !== FULL_AWARD;
	frm.set_df_property("items", "read_only", editable ? 0 : 1);
	frm.fields_dict.items.grid.cannot_add_rows = true;
}

function row_for(frm, rfq_item) {
	return (frm.doc.items || []).find((row) => row.request_for_quotation_item === rfq_item);
}

function apply_bid(row, bid) {
	for (const field of BID_FIELDS) row[field] = bid[field];
}

function award_item(frm, line, bid) {
	const row =
		row_for(frm, line.request_for_quotation_item) ||
		frm.add_child("items", {
			request_for_quotation_item: line.request_for_quotation_item,
			item_code: line.item_code,
			item_name: line.item_name,
			qty: line.qty,
			uom: line.uom,
		});
	apply_bid(row, bid);
}

function leave_open(frm, rfq_item) {
	frm.doc.items = (frm.doc.items || []).filter(
		(row) => row.request_for_quotation_item !== rfq_item
	);
	frm.doc.items.forEach((row, index) => (row.idx = index + 1));
}

function changed(frm) {
	frm.refresh_field("items");
	frm.dirty();
	render(frm);
}

function fill_best_bids(frm) {
	if (frm.doc.docstatus !== 0 || !frm.__overview) return;
	frm.clear_table("items");
	for (const line of lines(frm)) {
		const bid = line.top_bids.find((candidate) => !is_expired(frm, candidate));
		if (bid) award_item(frm, line, bid);
	}
	changed(frm);
}

function fill_from_quotation(frm) {
	if (frm.doc.docstatus !== 0 || !frm.__overview) return;
	frm.clear_table("items");
	if (!frm.doc.awarded_quotation) {
		changed(frm);
		return;
	}

	Promise.all(lines(frm).map((line) => item_bids(frm, line.request_for_quotation_item))).then(
		(all_bids) => {
			lines(frm).forEach((line, index) => {
				const bid = all_bids[index].find(
					(candidate) => candidate.supplier_quotation === frm.doc.awarded_quotation
				);
				if (bid) award_item(frm, line, bid);
			});
			changed(frm);
		}
	);
}

const esc = (value) => frappe.utils.escape_html(value == null ? "" : String(value));
const is_expired = (frm, quote) =>
	!!quote?.valid_till && !!frm.doc.award_date && quote.valid_till < frm.doc.award_date;
const qty = (value) => format_number(value, null, Number.isInteger(value) ? 0 : null);

function percent_above(value, lowest) {
	if (!lowest || !value || value <= lowest) return "";
	const percent = ((value - lowest) / lowest) * 100;
	return percent < 0.1 ? "+<0.1%" : `+${percent.toFixed(1)}%`;
}

function render(frm) {
	const wrapper = frm.get_field("comparison").$wrapper;
	const overview = frm.__overview;
	wrapper.off();
	if (!overview) {
		wrapper.empty();
		return;
	}

	if (frm.doc.docstatus === 0 && overview.blockers.length) {
		wrapper.html(
			`<div class="alert alert-warning">${overview.blockers.map(esc).join("<br>")}</div>`
		);
		return;
	}

	if (!overview.lines.length) {
		wrapper.html(`<p class="text-muted">${__("No open items left to award.")}</p>`);
		return;
	}

	const full = frm.doc.award_basis === FULL_AWARD;
	wrapper.html(`
		<style>${STYLE}</style>
		<div class="rfqa">
			${summary_html(frm)}
			${full ? quotes_html(frm) : items_html(frm)}
		</div>`);

	bind(frm, wrapper);
}

function summary_html(frm) {
	const currency = company_currency(frm);
	const stat = (label, value, note = "") => `
		<div class="rfqa-stat">
			<span class="rfqa-stat-label">${label}</span>
			<span class="rfqa-stat-value">${value}</span>
			${note ? `<span class="rfqa-stat-note">${note}</span>` : ""}
		</div>`;

	if (frm.doc.award_basis === FULL_AWARD) {
		const ranked = quotes(frm);
		const chosen = ranked.find(
			(quote) => quote.supplier_quotation === frm.doc.awarded_quotation
		);
		const gap = chosen ? chosen.base_total - ranked[0].base_total : 0;
		return `
			<div class="rfqa-summary">
				${stat(__("Open items"), lines(frm).length)}
				${stat(
					__("Complete quotations"),
					ranked.length,
					__("{0} suppliers quoted", [frm.__overview.supplier_count])
				)}
				${stat(
					__("Award value"),
					chosen ? format_currency(chosen.base_total, currency) : "—",
					chosen ? __("Rank {0}", [chosen.rank]) : __("Choose a quotation")
				)}
				${stat(
					__("Above lowest total"),
					gap > 0.005 ? format_currency(gap, currency) : __("None"),
					gap > 0.005 ? __("Fill in Justification below") : ""
				)}
			</div>`;
	}

	const items = lines(frm);
	const awarded = items.filter((line) => row_for(frm, line.request_for_quotation_item));
	const total = awarded.reduce(
		(sum, line) => sum + (row_for(frm, line.request_for_quotation_item).base_amount || 0),
		0
	);
	const best = awarded.reduce((sum, line) => sum + (line.top_bids[0]?.base_amount || 0), 0);
	const above = total - best;
	const to_justify = awarded.filter(
		(line) => !row_for(frm, line.request_for_quotation_item).is_lowest
	).length;

	return `
		<div class="rfqa-summary">
			${stat(
				__("Items awarded"),
				`${awarded.length} / ${items.length}`,
				awarded.length < items.length
					? __("{0} left open", [items.length - awarded.length])
					: ""
			)}
			${stat(__("Suppliers quoted"), frm.__overview.supplier_count)}
			${stat(__("Award value"), format_currency(total, currency))}
			${stat(
				__("Above best prices"),
				above > 0.005 ? format_currency(above, currency) : __("None"),
				to_justify === 1
					? __("1 item needs a justification")
					: to_justify
					? __("{0} items need a justification", [to_justify])
					: __("Every item at its lowest bid")
			)}
		</div>`;
}

function quotes_html(frm) {
	const editable = frm.doc.docstatus === 0;
	const ranked = quotes(frm);
	if (!ranked.length) {
		return `<div class="rfqa-list"><div class="rfqa-empty">${__(
			"No quotation prices every open item. Switch Award Basis to Partial Award to award item by item."
		)}</div></div>`;
	}

	const view = frm.__view;
	const lowest = ranked[0].base_total;
	const search = view.search.toLowerCase();
	const matches = ranked.filter(
		(quote) =>
			!search ||
			[quote.supplier_name, quote.supplier, quote.supplier_quotation].some((value) =>
				(value || "").toLowerCase().includes(search)
			)
	);
	const selected = matches.find(
		(quote) => quote.supplier_quotation === frm.doc.awarded_quotation
	);
	let shown = view.show_all_quotes || search ? matches : matches.slice(0, QUOTES_SHOWN);
	if (selected && !shown.includes(selected)) shown = [...shown, selected];

	const rows = shown
		.map((quote) => {
			const chosen = quote.supplier_quotation === frm.doc.awarded_quotation;
			const above = percent_above(quote.base_total, lowest);
			return `
				<div class="rfqa-quote ${chosen ? "selected" : ""}">
					<span class="rfqa-rank">${quote.rank}</span>
					<div>
						<div class="rfqa-item-name">${esc(quote.supplier_name || quote.supplier)}${
				quote.is_lowest ? `<span class="rfqa-tag lowest">${__("Lowest")}</span>` : ""
			}</div>
						<a class="rfqa-muted" href="${frappe.utils.get_form_link(
							"Supplier Quotation",
							quote.supplier_quotation
						)}">${esc(quote.supplier_quotation)}</a>
					</div>
					<div class="rfqa-right rfqa-hide-sm">${
						above ? `<span class="rfqa-tag above">${above}</span>` : ""
					}</div>
					<div class="rfqa-right"><b>${format_currency(quote.total, quote.currency)}</b></div>
					<div class="rfqa-right">${
						chosen
							? `<span class="indicator-pill green">${__("Selected")}</span>`
							: is_expired(frm, quote)
							? `<span class="indicator-pill gray">${__("Expired")}</span>`
							: editable
							? `<button class="btn btn-xs btn-default" data-action="award-all" data-quote="${esc(
									quote.supplier_quotation
							  )}">${__("Award All")}</button>`
							: ""
					}</div>
				</div>`;
		})
		.join("");

	const hidden = matches.length - shown.length;
	const tools =
		ranked.length > QUOTES_SHOWN
			? `<div class="rfqa-toolbar">
					<input class="form-control input-sm rfqa-search" data-action="search" placeholder="${__(
						"Search {0} suppliers",
						[ranked.length]
					)}" value="${esc(view.search)}">
					<span class="rfqa-muted">${__(
						"Cheapest first. Only quotations that price every open item."
					)}</span>
				</div>`
			: `<div class="rfqa-muted">${__(
					"Cheapest first. Only quotations that price every open item."
			  )}</div>`;

	return `
		${tools}
		<div class="rfqa-list ${shown.length > 12 ? "scroll" : ""}">${
		rows || `<div class="rfqa-empty">${__("No supplier matches.")}</div>`
	}</div>
		${
			hidden > 0
				? `<button class="rfqa-more" data-action="show-all-quotes">${__("Show {0} more", [
						hidden,
				  ])}</button>`
				: ""
		}`;
}

function items_html(frm) {
	const editable = frm.doc.docstatus === 0;
	const view = frm.__view;
	const all = lines(frm);
	const search = view.search.toLowerCase();
	const visible = all.filter((line) => {
		const awarded = !!row_for(frm, line.request_for_quotation_item);
		if (view.filter === "open" && awarded) return false;
		if (view.filter === "awarded" && !awarded) return false;
		return (
			!search ||
			[line.item_name, line.item_code].some((value) =>
				(value || "").toLowerCase().includes(search)
			)
		);
	});

	const open_count = all.filter((line) => !row_for(frm, line.request_for_quotation_item)).length;
	const tab = (key, label) =>
		`<button class="rfqa-tab ${
			view.filter === key ? "active" : ""
		}" data-action="filter" data-filter="${key}">${label}</button>`;

	const tools = `
		<div class="rfqa-toolbar">
			${
				all.length >= ITEM_TOOLS_FROM
					? `<input class="form-control input-sm rfqa-search" data-action="search" placeholder="${__(
							"Search {0} items",
							[all.length]
					  )}" value="${esc(view.search)}">
					<span class="rfqa-tabs">${tab("all", __("All"))}${tab(
							"open",
							__("Open ({0})", [open_count])
					  )}${tab("awarded", __("Awarded ({0})", [all.length - open_count]))}</span>`
					: `<span class="rfqa-muted">${
							editable
								? __(
										"Click a price to award that item. Items left open can be awarded later."
								  )
								: ""
					  }</span>`
			}
			<span class="rfqa-spacer"></span>
			${
				editable
					? `<button class="btn btn-xs btn-default" data-action="best-bids">${__(
							"Best Bid for Every Item"
					  )}</button>
					<button class="btn btn-xs btn-default" data-action="clear">${__("Clear")}</button>`
					: ""
			}
		</div>`;

	const rows = visible.map((line) => item_row_html(frm, line, editable)).join("");

	return `
		${tools}
		<div class="rfqa-list ${visible.length > 12 ? "scroll" : ""}">${
		rows || `<div class="rfqa-empty">${__("No items match.")}</div>`
	}</div>`;
}

function item_row_html(frm, line, editable) {
	const chosen = row_for(frm, line.request_for_quotation_item);
	const lowest = line.top_bids[0]?.base_rate;
	const shown = [...line.top_bids];
	if (chosen && !shown.some((bid) => bid.supplier_quotation === chosen.supplier_quotation)) {
		shown.splice(Math.min(shown.length, 3) - 1, 1, {
			...chosen,
			supplier_name: chosen.supplier,
		});
	}
	const more = line.bid_count - line.top_bids.length;

	const chips = shown
		.map((bid) => {
			const selected = chosen?.supplier_quotation === bid.supplier_quotation;
			const above = percent_above(bid.base_rate, lowest);
			const expired = is_expired(frm, bid);
			return `
				<button class="rfqa-bid ${selected ? "selected" : ""} ${expired ? "expired" : ""}" ${
				editable && !expired ? "" : "disabled"
			} data-action="pick" data-item="${esc(
				line.request_for_quotation_item
			)}" data-quote="${esc(bid.supplier_quotation)}" title="${esc(
				bid.supplier_name || bid.supplier
			)} · ${esc(bid.supplier_quotation)}">
					<span class="rfqa-bid-supplier">${esc(bid.supplier_name || bid.supplier)}</span>
					<span class="rfqa-bid-price">${format_currency(bid.rate, bid.currency)}${
				expired
					? `<span class="rfqa-tag expired">${__("Expired")}</span>`
					: bid.is_lowest
					? `<span class="rfqa-tag lowest">${__("Lowest")}</span>`
					: above
					? `<span class="rfqa-tag above">${above}</span>`
					: ""
			}</span>
				</button>`;
		})
		.join("");

	return `
		<div class="rfqa-row ${chosen ? "" : "open"}">
			<div>
				<div class="rfqa-item-name">${esc(line.item_name || line.item_code)}</div>
				<div class="rfqa-muted">${qty(line.qty)} ${esc(line.uom)} · ${__("{0} bids", [
		line.bid_count,
	])}</div>
				${status_html(chosen, lowest, editable, line)}
			</div>
			<div class="rfqa-bids">
				${chips || `<span class="rfqa-muted">${__("No bids")}</span>`}
				${
					more > 0
						? `<button class="rfqa-more" data-action="more" data-item="${esc(
								line.request_for_quotation_item
						  )}">${__("+{0} more", [more])}</button>`
						: ""
				}
			</div>
			${
				chosen && !chosen.is_lowest
					? `<div class="rfqa-justify">
						<textarea class="form-control" data-action="justify" data-item="${esc(
							line.request_for_quotation_item
						)}" placeholder="${__("Why {0} over the lowest price? Required.", [
							esc(chosen.supplier),
					  ])}" ${editable ? "" : "disabled"}>${esc(chosen.justification)}</textarea>
					</div>`
					: ""
			}
		</div>`;
}

function status_html(chosen, lowest, editable, line) {
	if (!chosen)
		return `<div class="rfqa-status"><span class="indicator-pill gray">${__(
			"Open"
		)}</span></div>`;

	const leave = editable
		? ` · <button class="rfqa-link" data-action="leave-open" data-item="${esc(
				line.request_for_quotation_item
		  )}">${__("Leave open")}</button>`
		: "";
	if (chosen.is_lowest) {
		return `<div class="rfqa-status good">✓ ${__("Lowest price")}${leave}</div>`;
	}
	return `<div class="rfqa-status warn">${__("{0} above lowest", [
		percent_above(chosen.base_rate, lowest),
	])}${leave}</div>`;
}

function bind(frm, wrapper) {
	const line_of = (element) =>
		lines(frm).find(
			(line) => line.request_for_quotation_item === $(element).attr("data-item")
		);

	wrapper.on(
		"input",
		"[data-action='search']",
		frappe.utils.debounce((event) => {
			frm.__view.search = event.target.value;
			const position = event.target.selectionStart;
			render(frm);
			const input = wrapper.find("[data-action='search']")[0];
			if (input) {
				input.focus();
				input.setSelectionRange(position, position);
			}
		}, 250)
	);

	wrapper.on("input", "[data-action='justify']", (event) => {
		const row = row_for(frm, $(event.currentTarget).attr("data-item"));
		if (!row) return;
		row.justification = event.target.value;
		event.target.classList.toggle("rfqa-missing", !event.target.value.trim());
		frm.dirty();
	});

	wrapper.on("click", "[data-action]", (event) => {
		if ($(event.currentTarget).attr("data-action") === "justify") return;
		const target = event.currentTarget;
		switch ($(target).attr("data-action")) {
			case "award-all":
				frm.set_value("awarded_quotation", $(target).attr("data-quote"));
				break;
			case "show-all-quotes":
				frm.__view.show_all_quotes = true;
				render(frm);
				break;
			case "filter":
				frm.__view.filter = $(target).attr("data-filter");
				render(frm);
				break;
			case "best-bids":
				fill_best_bids(frm);
				break;
			case "clear":
				frm.clear_table("items");
				changed(frm);
				break;
			case "leave-open":
				leave_open(frm, $(target).attr("data-item"));
				changed(frm);
				break;
			case "pick": {
				if (frm.doc.docstatus !== 0) return;
				const line = line_of(target);
				const quote = $(target).attr("data-quote");
				const bid =
					line.top_bids.find((candidate) => candidate.supplier_quotation === quote) ||
					(frm.__bids[line.request_for_quotation_item] || []).find(
						(candidate) => candidate.supplier_quotation === quote
					);
				if (bid) {
					award_item(frm, line, bid);
					changed(frm);
				}
				break;
			}
			case "more":
				show_bid_picker(frm, line_of(target));
				break;
		}
	});
}

function show_bid_picker(frm, line) {
	item_bids(frm, line.request_for_quotation_item).then((bids) => {
		const dialog = new frappe.ui.Dialog({
			title: __("Choose a supplier for {0}", [line.item_name || line.item_code]),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "picker" }],
		});
		const wrapper = dialog.fields_dict.picker.$wrapper;
		const chosen = row_for(frm, line.request_for_quotation_item);
		const lowest = bids[0]?.base_rate;
		const editable = frm.doc.docstatus === 0;
		let search = "";

		const draw = () => {
			const term = search.toLowerCase();
			const matches = bids.filter(
				(bid) =>
					!term ||
					[bid.supplier_name, bid.supplier, bid.supplier_quotation].some((value) =>
						(value || "").toLowerCase().includes(term)
					)
			);
			const rows = matches
				.slice(0, PICKER_ROWS)
				.map((bid) => {
					const selected = chosen?.supplier_quotation === bid.supplier_quotation;
					const above = percent_above(bid.base_rate, lowest);
					return `
						<div class="rfqa-quote ${selected ? "selected" : ""}">
							<span class="rfqa-rank">${bid.item_rank}</span>
							<div>
								<div class="rfqa-item-name">${esc(bid.supplier_name || bid.supplier)}${
						bid.is_lowest ? `<span class="rfqa-tag lowest">${__("Lowest")}</span>` : ""
					}</div>
								<span class="rfqa-muted">${esc(bid.supplier_quotation)}</span>
							</div>
							<div class="rfqa-right rfqa-hide-sm">${
								above ? `<span class="rfqa-tag above">${above}</span>` : ""
							}</div>
							<div class="rfqa-right"><b>${format_currency(bid.rate, bid.currency)}</b>
								<div class="rfqa-muted">${format_currency(bid.amount, bid.currency)}</div></div>
							<div class="rfqa-right">${
								selected
									? `<span class="indicator-pill green">${__("Selected")}</span>`
									: is_expired(frm, bid)
									? `<span class="indicator-pill gray">${__("Expired")}</span>`
									: editable
									? `<button class="btn btn-xs btn-primary" data-quote="${esc(
											bid.supplier_quotation
									  )}">${__("Award")}</button>`
									: ""
							}</div>
						</div>`;
				})
				.join("");
			wrapper
				.find(".rfqa-picker-list")
				.html(rows || `<div class="rfqa-empty">${__("No supplier matches.")}</div>`);
			wrapper
				.find(".rfqa-picker-count")
				.text(
					matches.length > PICKER_ROWS
						? __("Showing the cheapest {0} of {1}. Search to narrow down.", [
								PICKER_ROWS,
								matches.length,
						  ])
						: __("{0} bids, cheapest first.", [matches.length])
				);
		};

		wrapper.html(`
			<style>${STYLE}</style>
			<div class="rfqa">
				<div class="rfqa-toolbar">
					<input class="form-control input-sm rfqa-search" placeholder="${__("Search suppliers")}">
					<span class="rfqa-muted rfqa-picker-count"></span>
				</div>
				<div class="rfqa-muted">${__("{0} {1} requested.", [qty(line.qty), esc(line.uom)])}</div>
				<div class="rfqa-list scroll rfqa-picker-list"></div>
			</div>`);

		wrapper.find(".rfqa-search").on(
			"input",
			frappe.utils.debounce((event) => {
				search = event.target.value;
				draw();
			}, 200)
		);
		wrapper.on("click", "button[data-quote]", (event) => {
			const bid = bids.find(
				(candidate) =>
					candidate.supplier_quotation === $(event.currentTarget).attr("data-quote")
			);
			if (!bid) return;
			award_item(frm, line, bid);
			changed(frm);
			dialog.hide();
		});

		draw();
		dialog.show();
		setTimeout(() => wrapper.find(".rfqa-search").trigger("focus"), 200);
	});
}

function client_problems(frm) {
	const problems = [];
	const overview = frm.__overview;
	if (overview?.blockers.length) return overview.blockers.map(esc);

	if (frm.doc.award_basis === FULL_AWARD) {
		const quote = quotes(frm).find(
			(candidate) => candidate.supplier_quotation === frm.doc.awarded_quotation
		);
		if (!frm.doc.awarded_quotation) {
			problems.push(
				__("Choose the winning quotation, or use Award All on one of the quotations.")
			);
		} else if (overview && !quote) {
			problems.push(
				__(
					"{0} does not price every open item. Choose another quotation or use Partial Award.",
					[esc(frm.doc.awarded_quotation)]
				)
			);
		} else if (quote && is_expired(frm, quote)) {
			problems.push(
				__("{0} expired on {1}.", [
					esc(quote.supplier_quotation),
					frappe.datetime.str_to_user(quote.valid_till),
				])
			);
		} else if (quote && !quote.is_lowest && !(frm.doc.justification || "").trim()) {
			problems.push(
				__("{0} is not the lowest total. Explain why it wins in Justification.", [
					esc(quote.supplier_name || quote.supplier),
				])
			);
		}
		return problems;
	}

	const rows = frm.doc.items || [];
	if (!rows.length) {
		problems.push(
			__(
				"Award at least one item. Click a price on an item, or use Best Bid for Every Item."
			)
		);
	}
	const unjustified = rows.filter((row) => !row.is_lowest && !(row.justification || "").trim());
	if (unjustified.length) {
		problems.push(
			__("Explain why each of these wins over a lower price: {0}", [
				unjustified
					.map((row) => `<b>${esc(row.item_name || row.item_code)}</b>`)
					.join(", "),
			])
		);
	}
	return problems;
}

function point_at_missing_justification(frm) {
	const wrapper = frm.get_field("comparison").$wrapper;
	const find = () =>
		wrapper
			.find(".rfqa-justify textarea")
			.toArray()
			.filter((input) => !input.value.trim());
	let missing = find();
	if (!missing.length && (frm.__view.search || frm.__view.filter !== "all")) {
		frm.__view.search = "";
		frm.__view.filter = "all";
		render(frm);
		missing = find();
	}
	missing.forEach((input) => input.classList.add("rfqa-missing"));
	if (missing.length) {
		missing[0].scrollIntoView({ behavior: "smooth", block: "center" });
		setTimeout(() => missing[0].focus(), 400);
	}
}
