<script setup>
import { computed, onUnmounted, ref, watch } from "vue";
import { Alert, Badge, Button, Dropdown, TabButtons } from "frappe-ui";

const props = defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["title", "actions"]);

const frappe = window.frappe;
const __ = window.__;

const PAGE_NAME = "sourcing-home";
const WORKSPACE_NAME = "Sourcing";
const PORTAL_URL = "/vuna-sourcing";

const RFQ = "Request for Quotation";
const SUPPLIER_QUOTATION = "Supplier Quotation";
const AWARD = "Request for Quotation Award";
const ONBOARDING_REQUEST = "Party Onboarding Request";
const SALES_ORDER = "Sales Order";
const CREDIT_NOTE_REQUEST = "Credit Note Request";

const PENDING_REVIEW = "Pending Review";
const RETURNED_FOR_CORRECTION = "Returned for Correction";
const APPROVED = "Approved";
const SUBMITTED = "Submitted";

const QUEUE_PREVIEW_LIMIT = 6;
const REALTIME_DEBOUNCE_MS = 1500;

const relative_time = (row) => frappe.datetime.prettyDate(row.modified);
const money = (amount, currency) => window.format_currency(amount, currency);

const QUEUES = {
	applications: {
		doctype: ONBOARDING_REQUEST,
		label: __("Applications to review"),
		short_label: __("Applications"),
		hint: __("New suppliers and customers waiting for approval"),
		icon: "lucide-user-plus",
		theme: "amber",
		filters: { docstatus: 1, onboarding_status: PENDING_REVIEW },
		fields: ["name", "party_name", "party_type", "modified"],
		title: (row) => row.party_name || row.name,
		subtitle: (row) => [__(row.party_type), row.name].filter(Boolean).join(" · "),
		meta: relative_time,
		empty: __("No applications are waiting. New sign-ups from the portal appear here."),
	},
	waiting_on_applicants: {
		doctype: ONBOARDING_REQUEST,
		label: __("Sent back to applicants"),
		hint: __("Waiting for applicants to correct their details"),
		icon: "lucide-undo-2",
		filters: { docstatus: 1, onboarding_status: RETURNED_FOR_CORRECTION },
	},
	draft_rfqs: {
		doctype: RFQ,
		label: __("Draft"),
		hint: __("Not yet sent to suppliers"),
		filters: { docstatus: 0 },
	},
	open_rfqs: {
		doctype: RFQ,
		label: __("Open for bids"),
		hint: __("Suppliers are preparing quotations"),
		icon: "lucide-send",
		filters: { docstatus: 1 },
	},
	quotations: {
		doctype: SUPPLIER_QUOTATION,
		label: __("Quotations to evaluate"),
		short_label: __("Quotations"),
		hint: __("Submitted by suppliers and ready to compare"),
		icon: "lucide-scale",
		theme: "blue",
		filters: { docstatus: 0, supplier_submission_status: SUBMITTED },
		fields: ["name", "supplier_name", "grand_total", "currency", "modified"],
		title: (row) => row.supplier_name || row.name,
		subtitle: (row) => `${row.name} · ${money(row.grand_total, row.currency)}`,
		meta: relative_time,
		empty: __("No quotations to compare. They arrive here when suppliers submit bids."),
	},
	awards: {
		doctype: AWARD,
		label: __("Awards to finalise"),
		hint: __("Drafted awards that still need submitting"),
		icon: "lucide-award",
		theme: "violet",
		filters: { docstatus: 0 },
	},
	portal_orders: {
		doctype: SALES_ORDER,
		label: __("Portal orders to confirm"),
		short_label: __("Orders"),
		hint: __("Placed by customers on the portal"),
		icon: "lucide-shopping-cart",
		theme: "green",
		filters: { docstatus: 0, created_from_portal: 1, portal_submission_status: SUBMITTED },
		fields: ["name", "customer_name", "grand_total", "currency", "modified"],
		title: (row) => row.customer_name || row.name,
		subtitle: (row) => `${row.name} · ${money(row.grand_total, row.currency)}`,
		meta: relative_time,
		empty: __("No orders to confirm. Customer orders from the portal appear here."),
	},
	credit_requests: {
		doctype: CREDIT_NOTE_REQUEST,
		label: __("Credit requests to review"),
		short_label: __("Credit requests"),
		hint: __("Customers asking for a credit on an invoice"),
		icon: "lucide-receipt",
		theme: "red",
		filters: { docstatus: 1, request_status: PENDING_REVIEW },
		fields: ["name", "customer_name", "sales_invoice", "total_amount", "currency", "modified"],
		title: (row) => row.customer_name || row.name,
		subtitle: (row) =>
			[row.sales_invoice, money(row.total_amount, row.currency)].filter(Boolean).join(" · "),
		meta: relative_time,
		empty: __("No credit requests to review."),
	},
	credit_notes_to_issue: {
		doctype: CREDIT_NOTE_REQUEST,
		label: __("Credit notes to issue"),
		hint: __("Approved requests still waiting for a credit note"),
		icon: "lucide-file-check-2",
		theme: "gray",
		filters: { docstatus: 1, request_status: APPROVED },
	},
};

const ATTENTION_GROUPS = [
	{ label: __("Suppliers & customers"), queues: ["applications"] },
	{ label: __("Bidding"), queues: ["quotations", "awards"] },
	{
		label: __("Orders & credit"),
		queues: ["portal_orders", "credit_requests", "credit_notes_to_issue"],
	},
];
const PIPELINE = ["draft_rfqs", "open_rfqs", "quotations", "awards"];
const WAITING = ["waiting_on_applicants", "open_rfqs"];
const WORK_QUEUES = ["applications", "quotations", "portal_orders", "credit_requests"];

const GO_TO = [
	{ label: __("Requests for Quotation"), icon: "lucide-file-text", doctype: RFQ },
	{ label: __("Suppliers"), icon: "lucide-truck", doctype: "Supplier" },
	{ label: __("Customers"), icon: "lucide-users", doctype: "Customer" },
	{
		label: __("Onboarding requests"),
		icon: "lucide-clipboard-list",
		doctype: ONBOARDING_REQUEST,
	},
	{
		label: __("Opening committees"),
		icon: "lucide-shield-check",
		doctype: "RFQ Opening Committee",
	},
	{
		label: __("Sourcing settings"),
		icon: "lucide-settings",
		doctype: "Sourcing Settings",
		single: true,
	},
];

const can_read = (key) => frappe.model.can_read(QUEUES[key].doctype);
const readable = (keys) => keys.filter(can_read);

const counts = ref({});
const loading = ref(true);
const failed = ref(false);
const updated_at = ref(null);
const active_queue = ref(null);
const queue_rows = ref({});
const queue_loading = ref(false);

const attention_groups = computed(() =>
	ATTENTION_GROUPS.map((group) => ({ ...group, queues: readable(group.queues) })).filter(
		(group) => group.queues.length
	)
);
const pipeline = computed(() => readable(PIPELINE));
const waiting = computed(() => readable(WAITING));
const work_queues = computed(() => readable(WORK_QUEUES));
const go_to = computed(() => GO_TO.filter((link) => frappe.model.can_read(link.doctype)));

const needs_attention = computed(() =>
	attention_groups.value
		.flatMap((group) => group.queues)
		.reduce((sum, key) => sum + (counts.value[key] || 0), 0)
);
const pipeline_peak = computed(() =>
	Math.max(1, ...pipeline.value.map((key) => counts.value[key] || 0))
);

const greeting = computed(() => {
	const hour = new Date().getHours();
	const first_name = (frappe.session.user_fullname || "").split(" ")[0];
	const salutation =
		hour < 12 ? __("Good morning") : hour < 17 ? __("Good afternoon") : __("Good evening");
	return first_name ? `${salutation}, ${first_name}` : salutation;
});

const summary = computed(() => {
	if (loading.value) return __("Checking what needs you…");
	if (failed.value) return __("Some numbers could not be loaded.");
	if (!needs_attention.value) return __("You're all caught up. Nothing is waiting on you.");
	return needs_attention.value === 1
		? __("1 item is waiting on you.")
		: __("{0} items are waiting on you.", [needs_attention.value]);
});

const updated_label = computed(() =>
	updated_at.value
		? __("Updated {0}", [
				updated_at.value.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }),
		  ])
		: ""
);

const work_queue_tabs = computed(() =>
	work_queues.value.map((key) => ({
		value: key,
		label:
			counts.value[key] !== undefined
				? `${QUEUES[key].short_label} (${counts.value[key]})`
				: QUEUES[key].short_label,
	}))
);

const create_options = computed(() =>
	[
		{ label: __("Request for Quotation"), icon: "lucide-file-plus", doctype: RFQ },
		{ label: __("Supplier"), icon: "lucide-truck", doctype: "Supplier" },
		{ label: __("Customer"), icon: "lucide-user-round-plus", doctype: "Customer" },
	]
		.filter((option) => frappe.model.can_create(option.doctype))
		.map((option) => ({
			label: option.label,
			icon: option.icon,
			onClick: () => frappe.new_doc(option.doctype),
		}))
);

const can_create_rfq = computed(() => frappe.model.can_create(RFQ));

function count_queue(key) {
	const queue = QUEUES[key];
	return frappe.db.count(queue.doctype, { filters: queue.filters });
}

function load_counts() {
	const keys = Object.keys(QUEUES).filter(can_read);
	loading.value = !updated_at.value;
	failed.value = false;
	return Promise.allSettled(keys.map(count_queue)).then((results) => {
		const next = {};
		results.forEach((result, index) => {
			if (result.status === "fulfilled") next[keys[index]] = result.value;
			else failed.value = true;
		});
		counts.value = next;
		updated_at.value = new Date();
		loading.value = false;
	});
}

function load_queue(key) {
	if (!key) return;
	const queue = QUEUES[key];
	queue_loading.value = !queue_rows.value[key];
	return frappe.db
		.get_list(queue.doctype, {
			filters: queue.filters,
			fields: queue.fields,
			order_by: "modified desc",
			limit: QUEUE_PREVIEW_LIMIT,
		})
		.then(
			(rows) => (queue_rows.value = { ...queue_rows.value, [key]: rows }),
			() => (queue_rows.value = { ...queue_rows.value, [key]: null })
		)
		.finally(() => (queue_loading.value = false));
}

function refresh() {
	load_counts();
	load_queue(active_queue.value);
}

function pick_starting_queue() {
	if (active_queue.value && work_queues.value.includes(active_queue.value)) return;
	active_queue.value =
		work_queues.value.find((key) => counts.value[key] > 0) || work_queues.value[0] || null;
}

function open_list(key) {
	const queue = QUEUES[key];
	frappe.route_options = { ...queue.filters };
	frappe.set_route("List", queue.doctype);
}

function open_document(key, row) {
	frappe.set_route("Form", QUEUES[key].doctype, row.name);
}

function go(link) {
	if (link.single) frappe.set_route("Form", link.doctype);
	else frappe.set_route("List", link.doctype);
}

function bar_width(key) {
	const count = counts.value[key] || 0;
	return count ? `${Math.max(6, Math.round((count / pipeline_peak.value) * 100))}%` : "0%";
}

const watched_doctypes = [...new Set(Object.values(QUEUES).map((queue) => queue.doctype))];
let refresh_timer = null;

function on_list_update(data) {
	if (!watched_doctypes.includes(data?.doctype)) return;
	if (frappe.get_route()[0] !== PAGE_NAME) return;
	clearTimeout(refresh_timer);
	refresh_timer = setTimeout(refresh, REALTIME_DEBOUNCE_MS);
}

function listen_for_changes() {
	watched_doctypes.forEach((doctype) => frappe.realtime.doctype_subscribe(doctype));
	frappe.realtime.off("list_update", on_list_update);
	frappe.realtime.on("list_update", on_list_update);
}

function report_chrome() {
	emit("title", __("Sourcing"));
	emit("actions", [
		{ label: __("Refresh"), icon: "lucide-refresh-cw", onClick: refresh },
		{
			label: __("Open supplier & customer portal"),
			icon: "lucide-external-link",
			href: PORTAL_URL,
		},
		{
			label: __("Classic workspace"),
			icon: "lucide-layout-grid",
			onClick: () => frappe.set_route(frappe.router.slug(WORKSPACE_NAME)),
		},
	]);
}

watch(
	() => props.route,
	() => {
		report_chrome();
		listen_for_changes();
		load_counts().then(() => {
			pick_starting_queue();
			load_queue(active_queue.value);
		});
	},
	{ immediate: true }
);

watch(active_queue, (key, previous) => {
	if (previous !== null) load_queue(key);
});

onUnmounted(() => {
	clearTimeout(refresh_timer);
	frappe.realtime.off("list_update", on_list_update);
});
</script>

<template>
	<div class="h-full overflow-y-auto">
		<div class="mx-auto flex max-w-6xl flex-col gap-6 px-4 pt-5 pb-12 sm:px-6">
			<header class="flex flex-wrap items-end justify-between gap-4">
				<div class="min-w-0">
					<h1 class="text-xl font-semibold text-ink-gray-9">{{ greeting }}</h1>
					<p class="mt-1 text-base text-ink-gray-6" aria-live="polite">{{ summary }}</p>
				</div>
				<div class="flex items-center gap-2">
					<span v-if="updated_label" class="hidden text-sm text-ink-gray-5 sm:inline">
						{{ updated_label }}
					</span>
					<Button
						:tooltip="__('Refresh')"
						:aria-label="__('Refresh')"
						:loading="loading"
						@click="refresh"
					>
						<i class="lucide-refresh-cw" aria-hidden="true" />
					</Button>
					<Dropdown
						v-if="create_options.length > 1"
						:options="create_options"
						align="end"
						:button="{ label: __('New'), variant: 'subtle' }"
					/>
					<Button v-if="can_create_rfq" variant="solid" @click="frappe.new_doc(RFQ)">
						<template #prefix
							><i class="lucide-plus size-4" aria-hidden="true"
						/></template>
						{{ __("New RFQ") }}
					</Button>
				</div>
			</header>

			<Alert
				v-if="failed && !loading"
				theme="red"
				:title="__('Some numbers could not be loaded')"
				:description="
					__('The counts shown may be incomplete. Check your connection and refresh.')
				"
			/>

			<section v-if="attention_groups.length" aria-labelledby="attention-heading">
				<h2 id="attention-heading" class="mb-3 text-base font-semibold text-ink-gray-8">
					{{ __("Needs your attention") }}
				</h2>
				<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
					<template v-for="group in attention_groups" :key="group.label">
						<button
							v-for="key in group.queues"
							:key="key"
							type="button"
							class="group flex items-start gap-3 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 p-4 text-left transition hover:border-outline-gray-3 hover:bg-surface-gray-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-4"
							:aria-label="`${QUEUES[key].label}: ${counts[key] ?? 0}`"
							@click="open_list(key)"
						>
							<span
								class="flex size-9 shrink-0 items-center justify-center rounded-4 bg-surface-gray-2 text-ink-gray-7"
							>
								<i :class="[QUEUES[key].icon, 'size-4']" aria-hidden="true" />
							</span>
							<span class="min-w-0 flex-1">
								<span class="block text-xs font-medium text-ink-gray-5">
									{{ group.label }}
								</span>
								<span class="mt-0.5 block text-base font-medium text-ink-gray-9">
									{{ QUEUES[key].label }}
								</span>
								<span class="mt-0.5 block text-sm text-ink-gray-6">
									{{ QUEUES[key].hint }}
								</span>
							</span>
							<span
								v-if="loading"
								class="h-7 w-9 shrink-0 animate-pulse rounded-3 bg-surface-gray-2"
							/>
							<Badge
								v-else-if="counts[key]"
								:theme="QUEUES[key].theme"
								variant="subtle"
								size="lg"
							>
								{{ counts[key] }}
							</Badge>
							<span
								v-else
								class="flex shrink-0 items-center gap-1 text-sm text-ink-gray-5"
							>
								<i class="lucide-check size-4" aria-hidden="true" />
								{{ __("Clear") }}
							</span>
						</button>
					</template>
				</div>
			</section>

			<div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
				<section
					v-if="work_queues.length"
					class="flex min-w-0 flex-col rounded-6 border border-outline-gray-2 bg-surface-elevation-2 lg:col-span-2"
					aria-labelledby="queue-heading"
				>
					<div class="flex flex-col gap-3 border-b border-outline-gray-1 p-4">
						<h2 id="queue-heading" class="text-base font-semibold text-ink-gray-8">
							{{ __("Work queue") }}
						</h2>
						<div class="-mx-1 overflow-x-auto px-1">
							<TabButtons v-model="active_queue" :options="work_queue_tabs" />
						</div>
					</div>

					<div v-if="!active_queue || queue_loading" class="space-y-2 p-4">
						<div
							v-for="row in 4"
							:key="row"
							class="h-12 animate-pulse rounded-4 bg-surface-gray-2"
						/>
					</div>

					<div
						v-else-if="queue_rows[active_queue] === null"
						class="flex flex-col items-center gap-3 px-4 py-10 text-center"
					>
						<p class="text-base text-ink-gray-6">
							{{ __("This list could not be loaded.") }}
						</p>
						<Button @click="load_queue(active_queue)">{{ __("Try again") }}</Button>
					</div>

					<div
						v-else-if="!queue_rows[active_queue]?.length"
						class="flex flex-col items-center gap-2 px-4 py-10 text-center"
					>
						<span
							class="flex size-10 items-center justify-center rounded-full bg-surface-gray-2 text-ink-gray-6"
						>
							<i class="lucide-inbox size-5" aria-hidden="true" />
						</span>
						<p class="text-base font-medium text-ink-gray-8">
							{{ __("Nothing to do here") }}
						</p>
						<p class="max-w-sm text-sm text-ink-gray-6">
							{{ QUEUES[active_queue].empty }}
						</p>
					</div>

					<ul v-else class="flex-1 divide-y divide-outline-gray-1">
						<li v-for="row in queue_rows[active_queue]" :key="row.name">
							<button
								type="button"
								class="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-gray-1 focus-visible:bg-surface-gray-2 focus-visible:outline-none"
								@click="open_document(active_queue, row)"
							>
								<span class="min-w-0 flex-1">
									<span
										class="block truncate text-base font-medium text-ink-gray-8"
									>
										{{ QUEUES[active_queue].title(row) }}
									</span>
									<span class="mt-0.5 block truncate text-sm text-ink-gray-5">
										{{ QUEUES[active_queue].subtitle(row) }}
									</span>
								</span>
								<span class="shrink-0 text-sm text-ink-gray-5">
									{{ QUEUES[active_queue].meta(row) }}
								</span>
								<i
									class="lucide-chevron-right size-4 shrink-0 text-ink-gray-4"
									aria-hidden="true"
								/>
							</button>
						</li>
					</ul>

					<div
						v-if="active_queue && counts[active_queue] > QUEUE_PREVIEW_LIMIT"
						class="border-t border-outline-gray-1 p-2"
					>
						<Button variant="ghost" class="w-full" @click="open_list(active_queue)">
							{{ __("View all {0}", [counts[active_queue]]) }}
						</Button>
					</div>
				</section>

				<div class="flex min-w-0 flex-col gap-6">
					<section
						v-if="pipeline.length"
						class="rounded-6 border border-outline-gray-2 bg-surface-elevation-2 p-4"
						aria-labelledby="pipeline-heading"
					>
						<h2 id="pipeline-heading" class="text-base font-semibold text-ink-gray-8">
							{{ __("RFQ pipeline") }}
						</h2>
						<p class="mt-0.5 text-sm text-ink-gray-5">
							{{ __("From request to award") }}
						</p>
						<ol class="mt-3 space-y-1">
							<li v-for="(key, index) in pipeline" :key="key">
								<button
									type="button"
									class="w-full rounded-4 p-2 text-left hover:bg-surface-gray-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-4"
									@click="open_list(key)"
								>
									<span class="flex items-center justify-between gap-2">
										<span class="flex min-w-0 items-center gap-2">
											<span
												class="flex size-5 shrink-0 items-center justify-center rounded-full bg-surface-gray-2 text-xs font-medium text-ink-gray-6"
											>
												{{ index + 1 }}
											</span>
											<span
												class="truncate text-sm font-medium text-ink-gray-8"
											>
												{{ QUEUES[key].short_label || QUEUES[key].label }}
											</span>
										</span>
										<span
											v-if="loading"
											class="h-4 w-6 animate-pulse rounded-3 bg-surface-gray-2"
										/>
										<span v-else class="text-sm font-semibold text-ink-gray-8">
											{{ counts[key] ?? 0 }}
										</span>
									</span>
									<span
										class="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-surface-gray-2"
									>
										<span
											class="block h-full rounded-full bg-surface-gray-7 transition-all"
											:style="{ width: loading ? '0%' : bar_width(key) }"
										/>
									</span>
								</button>
							</li>
						</ol>
					</section>

					<section
						v-if="waiting.length"
						class="rounded-6 border border-outline-gray-2 bg-surface-elevation-2 p-4"
						aria-labelledby="waiting-heading"
					>
						<h2 id="waiting-heading" class="text-base font-semibold text-ink-gray-8">
							{{ __("Waiting on others") }}
						</h2>
						<ul class="mt-2 space-y-1">
							<li v-for="key in waiting" :key="key">
								<button
									type="button"
									class="flex w-full items-center gap-3 rounded-4 p-2 text-left hover:bg-surface-gray-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-4"
									@click="open_list(key)"
								>
									<i
										:class="[
											QUEUES[key].icon,
											'size-4 shrink-0 text-ink-gray-5',
										]"
										aria-hidden="true"
									/>
									<span class="min-w-0 flex-1">
										<span
											class="block truncate text-sm font-medium text-ink-gray-8"
										>
											{{ QUEUES[key].label }}
										</span>
										<span class="block truncate text-xs text-ink-gray-5">
											{{ QUEUES[key].hint }}
										</span>
									</span>
									<span class="text-sm font-semibold text-ink-gray-7">
										{{ loading ? "–" : counts[key] ?? 0 }}
									</span>
								</button>
							</li>
						</ul>
					</section>

					<section
						v-if="go_to.length"
						class="rounded-6 border border-outline-gray-2 bg-surface-elevation-2 p-4"
						aria-labelledby="goto-heading"
					>
						<h2 id="goto-heading" class="text-base font-semibold text-ink-gray-8">
							{{ __("Go to") }}
						</h2>
						<ul class="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-1">
							<li v-for="link in go_to" :key="link.doctype">
								<button
									type="button"
									class="flex w-full items-center gap-2 rounded-4 p-2 text-left text-sm text-ink-gray-7 hover:bg-surface-gray-1 hover:text-ink-gray-9 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-4"
									@click="go(link)"
								>
									<i
										:class="[link.icon, 'size-4 shrink-0']"
										aria-hidden="true"
									/>
									<span class="truncate">{{ link.label }}</span>
								</button>
							</li>
						</ul>
					</section>
				</div>
			</div>

			<p
				v-if="
					!loading && !attention_groups.length && !work_queues.length && !pipeline.length
				"
				class="rounded-6 border border-outline-gray-2 p-6 text-center text-base text-ink-gray-6"
			>
				{{
					__(
						"Your role doesn't include any sourcing records yet. Ask your administrator for access."
					)
				}}
			</p>
		</div>
	</div>
</template>
