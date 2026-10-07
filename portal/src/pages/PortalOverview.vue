<script setup lang="ts">
import { computed, watch } from "vue";
import { Badge, Button, createResource } from "frappe-ui";
import { BarChart, DonutChart, NumberCard } from "frappe-ui/charts";
import PageContainer from "@/components/PageContainer.vue";
import { money, shortDate } from "@/data/purchase";
import { rfqRoute } from "@/data/rfq";
import { usePortalStore } from "@/stores/portal";

const portal = usePortalStore();

const party = createResource({
	url: "vuna_sourcing.api.portal.get_party",
	auto: false,
});

const supplierDashboard = createResource({
	url: "vuna_sourcing.api.transactions.supplier.get_dashboard",
	auto: false,
});

const customerDashboard = createResource({
	url: "vuna_sourcing.api.transactions.customer.get_dashboard",
	auto: false,
});

const isSupplier = computed(() => portal.activeParty?.party_type === "Supplier");
const dashboard = computed(() => (isSupplier.value ? supplierDashboard : customerDashboard));
const data = computed(() => dashboard.value.data ?? null);

function load() {
	const active = portal.activeParty;
	if (!active) return;
	party.fetch({ party_type: active.party_type, party: active.name });
	if (active.party_type === "Supplier") supplierDashboard.fetch({ supplier: active.name });
	else customerDashboard.fetch({ customer: active.name });
}

watch(() => portal.activePartyKey, load, { immediate: true });

const compact = new Intl.NumberFormat(undefined, {
	notation: "compact",
	maximumFractionDigits: 1,
});

function amount(value: number) {
	return money(value, data.value?.balance?.currency ?? data.value?.currency);
}

const cards = computed(() => {
	const d = data.value;
	if (!d) return [];
	if (isSupplier.value) {
		return [
			{ title: "Open RFQs", value: d.awaiting_quote, route: "RfqList" },
			{ title: "Open Orders", value: d.open_orders, route: "PurchaseOrderList" },
			{
				title: "Outstanding",
				value: d.balance.outstanding,
				format: amount,
				route: "SupplierStatement",
			},
			{
				title: "Paid (12 months)",
				value: d.paid_last_year,
				format: amount,
				route: "PurchaseInvoiceList",
			},
		];
	}
	return [
		{ title: "Open Quotations", value: d.quotes_to_review, route: "QuotationList" },
		{ title: "Open Orders", value: d.open_orders, route: "SalesOrderList" },
		{
			title: "Outstanding",
			value: d.balance.outstanding,
			format: amount,
			route: "CustomerStatement",
		},
		{ title: "Overdue", value: d.balance.overdue, format: amount, route: "CustomerStatement" },
	];
});

const trend = computed(() => {
	const rows =
		(isSupplier.value ? data.value?.orders_by_month : data.value?.invoiced_by_month) ?? [];
	return rows.map((row: { month: string; value: number }) => ({
		month: row.month,
		Amount: row.value,
	}));
});

const invoiceStatuses = computed(() => data.value?.invoices_by_status ?? []);

const lists = computed(() => {
	const d = data.value;
	if (!d) return [];
	if (isSupplier.value) {
		return [
			{
				title: "Open RFQs",
				all: "RfqList",
				rows: d.rfqs_closing.map((row: any) => ({
					name: row.name,
					route: rfqRoute(row),
					detail: `${row.status === "Bidding" ? "Bidding · c" : "C"}loses ${shortDate(
						row.closes_at
					)}`,
					trailing: `${row.items} item${row.items === 1 ? "" : "s"}`,
				})),
			},
			{
				title: "Open Orders",
				all: "PurchaseOrderList",
				rows: d.open_order_rows.map((row: any) => ({
					name: row.name,
					route: { name: "PurchaseOrderDetail", params: { name: row.name } },
					detail: `${shortDate(row.transaction_date)} · ${row.received}% received`,
					trailing: money(row.grand_total, row.currency),
				})),
			},
		];
	}
	return [
		{
			title: "Open Quotations",
			all: "QuotationList",
			rows: d.quotes.map((row: any) => ({
				name: row.name,
				route: { name: "QuotationDetail", params: { name: row.name } },
				detail: row.valid_till ? `Valid until ${shortDate(row.valid_till)}` : "",
				trailing: money(row.grand_total, row.currency),
			})),
		},
		{
			title: "Pending Deliveries",
			all: "SalesOrderList",
			rows: d.to_deliver.map((row: any) => ({
				name: row.name,
				route: { name: "SalesOrderDetail", params: { name: row.name } },
				detail: `Due ${shortDate(row.delivery_date)} · ${row.delivered}% delivered`,
				trailing: money(row.grand_total, row.currency),
			})),
		},
	];
});

const details = computed(() => {
	const d = party.data;
	if (!d) return [];
	return [
		["Type", d.entity_type || d.party_type],
		[`${d.party_type} Group`, d.group],
		...(d.party_type === "Customer" ? [["Territory", d.territory]] : []),
		["Country", d.country],
		["Currency", d.default_currency],
		["Tax ID", d.tax_id],
		["Website", d.website],
	];
});
</script>

<template>
	<PageContainer wide :title="portal.activeParty?.title || 'Overview'">
		<template #actions>
			<Badge
				v-if="portal.activeParty"
				theme="gray"
				variant="subtle"
				:label="portal.activeParty.party_type"
			/>
			<Button
				v-if="portal.activeParty"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="dashboard.loading"
				@click="load"
			/>
		</template>

		<div class="space-y-6">
			<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
				<template v-if="cards.length">
					<RouterLink
						v-for="card in cards"
						:key="card.title"
						:to="{ name: card.route }"
						class="rounded-6 transition-shadow hover:shadow-sm"
					>
						<NumberCard
							:title="card.title"
							:value="card.value"
							:format="card.format"
						/>
					</RouterLink>
				</template>
				<template v-else>
					<NumberCard v-for="index in 4" :key="index" title="" :value="null" loading />
				</template>
			</div>

			<div class="grid gap-3 lg:grid-cols-3">
				<div class="h-80 lg:col-span-2">
					<BarChart
						:title="isSupplier ? 'Purchase Orders' : 'Sales Invoices'"
						subtitle="Last 12 months"
						:data="trend"
						x="month"
						y="Amount"
						:x-axis="{ timeGrain: 'month' }"
						:y-axis="{ format: (value: number) => compact.format(value) }"
						:loading="dashboard.loading && !data"
					/>
				</div>
				<div class="h-80">
					<DonutChart
						title="Invoices by Status"
						:data="invoiceStatuses"
						category="status"
						value="count"
						center-label="Invoices"
						:loading="dashboard.loading && !data"
					/>
				</div>
			</div>

			<div class="grid gap-3 lg:grid-cols-2">
				<section v-for="list in lists" :key="list.title" class="rounded-6 border">
					<header class="flex items-center justify-between border-b px-4 py-3">
						<h2 class="text-base font-semibold text-ink-gray-8">{{ list.title }}</h2>
						<RouterLink
							:to="{ name: list.all }"
							class="text-p-sm text-ink-gray-6 hover:text-ink-gray-8"
						>
							View all
						</RouterLink>
					</header>
					<p v-if="!list.rows.length" class="px-4 py-6 text-p-sm text-ink-gray-5">
						None
					</p>
					<div v-else class="divide-y">
						<RouterLink
							v-for="row in list.rows"
							:key="row.name"
							:to="row.route"
							class="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-surface-gray-1"
						>
							<span class="min-w-0">
								<span class="block truncate text-base text-ink-gray-8">{{
									row.name
								}}</span>
								<span
									v-if="row.detail"
									class="block truncate text-xs text-ink-gray-5"
								>
									{{ row.detail }}
								</span>
							</span>
							<span class="shrink-0 text-p-sm text-ink-gray-7">{{
								row.trailing
							}}</span>
						</RouterLink>
					</div>
				</section>
			</div>

			<section v-if="details.length" class="rounded-6 border p-4">
				<h2 class="mb-3 text-base font-semibold text-ink-gray-8">Account Details</h2>
				<dl class="grid gap-x-6 gap-y-3 sm:grid-cols-3">
					<div v-for="row in details" :key="row[0] as string">
						<dt class="text-xs uppercase tracking-wide text-ink-gray-5">
							{{ row[0] }}
						</dt>
						<dd class="text-p-base text-ink-gray-8">{{ row[1] || "—" }}</dd>
					</div>
				</dl>
			</section>
		</div>
	</PageContainer>
</template>
