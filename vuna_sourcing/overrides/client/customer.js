const BRANCHES_FIELD = "branches";
const SEARCH_BRANCHES = "vuna_sourcing.overrides.server.customer.search_branches";
const SEARCH_DELAY = 300;

function parse_branches(value) {
	return (value || "")
		.split("\n")
		.map((branch) => branch.trim())
		.filter(Boolean);
}

function search_branches(customer, txt, selected) {
	return frappe
		.call({ method: SEARCH_BRANCHES, args: { customer, txt, selected } })
		.then(({ message }) => message?.data || []);
}

async function pick_branches(frm, row) {
	if (frm.is_new()) {
		frappe.msgprint(__("Save the customer and add its shipping addresses first."));
		return;
	}

	const chosen = parse_branches(row[BRANCHES_FIELD]);
	const options = await search_branches(frm.doc.name, "", chosen);
	if (!options.length) {
		frappe.msgprint(
			__(
				"This customer has no shipping addresses yet. Add a shipping address for each branch first."
			)
		);
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Branches for {0}", [row.user]),
		fields: [
			{
				fieldname: BRANCHES_FIELD,
				fieldtype: "MultiSelectPills",
				label: __("Branches"),
				description: __(
					"Type to search shipping addresses by name, street or city. Leave empty to give this user every branch."
				),
				options,
				default: chosen,
			},
		],
		primary_action_label: __("Set Branches"),
		primary_action(values) {
			frappe.model.set_value(
				row.doctype,
				row.name,
				BRANCHES_FIELD,
				(values[BRANCHES_FIELD] || []).join("\n")
			);
			dialog.hide();
		},
	});

	const picker = dialog.fields_dict[BRANCHES_FIELD];
	let latest = 0;
	const search = frappe.utils.debounce((txt) => {
		const request = ++latest;
		search_branches(frm.doc.name, txt, picker.get_value()).then((results) => {
			if (request === latest) picker.set_data(results);
		});
	}, SEARCH_DELAY);

	picker.$input.on("input", (event) => search(event.target.value));
	picker.$input.on("awesomplete-selectcomplete", () => {
		setTimeout(() => picker.awesomplete.close());
	});
	dialog.show();
}

frappe.ui.form.on("Portal User", {
	pick_branches(frm, cdt, cdn) {
		pick_branches(frm, locals[cdt][cdn]);
	},
});
