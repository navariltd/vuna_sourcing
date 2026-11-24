const PORTAL_VISIBILITY = "vuna_sourcing.overrides.server.item.get_portal_visibility";
const RECHECK_DELAY = 400;

const STATUS_INDICATOR = { passed: "green", failed: "red", skipped: "gray" };

function visibility_summary(result) {
	if (result.shown) {
		return {
			color: "green",
			title: __("Customers can see and order this item"),
			text: result.customer
				? __("It is offered to {0} when ordering from {1}.", [
						frappe.utils.escape_html(result.customer),
						frappe.utils.escape_html(result.company),
				  ])
				: __("It is offered when ordering from {0}.", [
						frappe.utils.escape_html(result.company),
				  ]),
		};
	}

	if (result.blocking) {
		return {
			color: "red",
			title:
				result.blocking === 1
					? __("Hidden from the portal: 1 thing to fix")
					: __("Hidden from the portal: {0} things to fix", [result.blocking]),
			text: __("Fix the items marked in red below. Each one on its own keeps it hidden."),
		};
	}

	return {
		color: "orange",
		title: __("Hidden from the portal"),
		text: __(
			"Every check passed, but the portal still leaves it out. Check the stock unit and prices, or ask your developer."
		),
	};
}

function check_row(check, index) {
	const action = check.action
		? `<button class="btn btn-xs btn-default portal-fix" data-index="${index}">
				${frappe.utils.escape_html(check.action.label)}
			</button>`
		: "";

	return `
		<div class="portal-check d-flex align-items-start justify-content-between">
			<div class="portal-check-text">
				<div class="indicator ${STATUS_INDICATOR[check.status] || "gray"}">${check.label}</div>
				<div class="portal-check-detail text-muted small">${check.detail}</div>
			</div>
			<div class="portal-check-action">${action}</div>
		</div>`;
}

function report_html(result, actions, dirty) {
	const summary = visibility_summary(result);
	let index = 0;

	const sections = result.sections
		.map((section) => {
			const rows = section.checks
				.map((check) => {
					actions.push(check.action);
					return check_row(check, index++);
				})
				.join("");
			const open = section.checks.some((check) => check.status === "failed");
			return `
				<div class="portal-section">
					<div class="portal-section-title">
						${frappe.utils.escape_html(section.label)}
						${open ? `<span class="indicator-pill red">${__("Needs attention")}</span>` : ""}
					</div>
					${rows}
				</div>`;
		})
		.join("");

	const unsaved = dirty
		? `<div class="alert alert-warning small mb-3">
				${__("This item has unsaved changes. The check uses the saved item, so save it first.")}
			</div>`
		: "";

	return `
		<div class="portal-visibility">
			${unsaved}
			<div class="portal-summary portal-summary-${summary.color}">
				<div class="indicator ${summary.color} portal-summary-title">${summary.title}</div>
				<div class="text-muted small">${summary.text}</div>
			</div>
			${sections}
		</div>`;
}

function loading_html() {
	return `
		<div class="portal-visibility portal-loading text-muted">
			<div class="portal-summary">${__("Checking where this item stands on the portal...")}</div>
			${'<div class="portal-skeleton"></div>'.repeat(6)}
		</div>`;
}

function error_html(message) {
	return `
		<div class="portal-visibility">
			<div class="portal-summary portal-summary-red">
				<div class="indicator red portal-summary-title">${__("We could not check this item")}</div>
				<div class="text-muted small">${frappe.utils.escape_html(message || "")}</div>
			</div>
			<button class="btn btn-sm btn-default portal-retry">${__("Try again")}</button>
		</div>`;
}

const STYLE = `
	.portal-visibility .portal-summary { border-radius: var(--border-radius-md); padding: var(--padding-md); margin-bottom: var(--margin-lg); background: var(--subtle-fg); }
	.portal-visibility .portal-summary-green { background: var(--green-highlight-color, var(--subtle-fg)); }
	.portal-visibility .portal-summary-red { background: var(--red-highlight-color, var(--subtle-fg)); }
	.portal-visibility .portal-summary-orange { background: var(--orange-highlight-color, var(--subtle-fg)); }
	.portal-visibility .portal-summary-title { font-weight: var(--weight-semibold); margin-bottom: 4px; }
	.portal-visibility .portal-section { margin-bottom: var(--margin-md); }
	.portal-visibility .portal-section-title { display: flex; gap: 8px; align-items: center; font-size: var(--text-xs); font-weight: var(--weight-semibold); text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); margin-bottom: 4px; }
	.portal-visibility .portal-check { gap: var(--margin-md); padding: 8px 0; border-bottom: 1px solid var(--border-color); }
	.portal-visibility .portal-check:last-child { border-bottom: none; }
	.portal-visibility .portal-check-text { min-width: 0; }
	.portal-visibility .portal-check-detail { margin-top: 2px; padding-left: 14px; overflow-wrap: anywhere; }
	.portal-visibility .portal-check-action { flex-shrink: 0; }
	.portal-visibility .portal-skeleton { height: 36px; margin-bottom: 8px; border-radius: var(--border-radius); background: var(--subtle-fg); animation: portal-pulse 1.2s ease-in-out infinite; }
	.portal-visibility.portal-stale { opacity: 0.5; pointer-events: none; }
	@keyframes portal-pulse { 50% { opacity: 0.5; } }
`;

function ensure_style() {
	if (document.getElementById("portal-visibility-style")) return;
	const style = document.createElement("style");
	style.id = "portal-visibility-style";
	style.textContent = STYLE;
	document.head.appendChild(style);
}

function open_portal_visibility(frm) {
	ensure_style();

	let actions = [];
	let latest = 0;
	let settling = false;

	const dialog = new frappe.ui.Dialog({
		title: __("Sourcing Portal: {0}", [
			frappe.utils.escape_html(frm.doc.item_name || frm.doc.name),
		]),
		size: "large",
		fields: [
			{
				fieldname: "company",
				fieldtype: "Link",
				options: "Company",
				label: __("Ordering from company"),
				description: __("Starts with the Default Ordering Company."),
				onchange: () => !settling && schedule(),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "customer",
				fieldtype: "Link",
				options: "Customer",
				label: __("For customer (optional)"),
				description: __("Also checks their companies and their own prices."),
				onchange: () => !settling && schedule(),
			},
			{ fieldtype: "Section Break" },
			{ fieldname: "report", fieldtype: "HTML" },
		],
		primary_action_label: __("Check again"),
		primary_action: () => load(),
	});

	const report = dialog.fields_dict.report.$wrapper;

	function show(html) {
		report.html(html);
	}

	function load() {
		const request = ++latest;
		const current = report.find(".portal-visibility");
		if (current.length && !current.hasClass("portal-loading"))
			current.addClass("portal-stale");
		else show(loading_html());
		dialog.get_primary_btn().prop("disabled", true);

		return frappe
			.call({
				method: PORTAL_VISIBILITY,
				args: {
					item: frm.doc.name,
					company: dialog.get_value("company") || null,
					customer: dialog.get_value("customer") || null,
				},
			})
			.then(({ message }) => {
				if (request !== latest) return;
				const result = message.data;
				actions = [];
				show(report_html(result, actions, frm.is_dirty()));
				if (!dialog.get_value("company") && result.company) {
					settling = true;
					dialog.set_value("company", result.company).then(() => (settling = false));
				}
			})
			.catch((error) => {
				if (request !== latest) return;
				show(error_html(error?.message || __("Please try again.")));
			})
			.finally(() => {
				if (request === latest) dialog.get_primary_btn().prop("disabled", false);
			});
	}

	const schedule = frappe.utils.debounce(load, RECHECK_DELAY);

	function run_fix(action, button) {
		if (!action) return;

		if (action.kind === "set_field") {
			button.prop("disabled", true).text(__("Saving..."));
			frm.set_value(action.field, action.value)
				.then(() => frm.save())
				.then(load)
				.catch(() => button.prop("disabled", false).text(action.label));
			return;
		}

		if (action.kind === "set_value") {
			button.prop("disabled", true).text(__("Saving..."));
			frappe.db
				.set_value(action.doctype, action.name, action.field, action.value)
				.then(load)
				.catch(() => button.prop("disabled", false).text(action.label));
			return;
		}

		dialog.hide();
		if (action.kind === "focus") frm.scroll_to_field(action.field);
		else if (action.kind === "variants")
			frappe.set_route("List", "Item", { variant_of: action.item });
		else if (action.kind === "new") frappe.new_doc(action.doctype, action.values);
		else if (action.route) frappe.set_route(...action.route);
		else frappe.set_route("Form", action.doctype, action.name);
	}

	report.on("click", ".portal-fix", (event) => {
		const button = $(event.currentTarget);
		run_fix(actions[Number(button.data("index"))], button);
	});
	report.on("click", ".portal-retry", () => load());

	dialog.show();
	load();
}

frappe.ui.form.on("Item", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Sourcing"), () => open_portal_visibility(frm));
	},
});
