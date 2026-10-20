<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, Spinner, TabButtons } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import ListFilters from "@/components/ListFilters.vue";
import { money, shortDate } from "@/data/purchase";
import type { PurchasePage } from "@/data/purchase";
import { SALES_ORDER_STATUS_THEME, salesOrderList } from "@/data/selling";
import type { SalesOrderRow } from "@/data/selling";
import { usePortalStore } from "@/stores/portal";
import { useIsMobile } from "@/composables/useViewport";
import { LOOKS } from "@/data/accents";

const portal = usePortalStore();
const isMobile = useIsMobile();

const filters = ref<Record<string, string>>({});
const pageLength = ref(20);

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const page = computed<(PurchasePage<SalesOrderRow> & { can_order: boolean }) | null>(
	() => salesOrderList.data ?? null
);
const canOrder = computed(() => !!page.value?.can_order);
const rows = computed<SalesOrderRow[]>(() => page.value?.rows ?? []);

function load() {
	if (!customer.value) {
		salesOrderList.reset();
		return;
	}

	salesOrderList.fetch({
		customer: customer.value,
		search: filters.value.search || null,
		start: 0,
		limit: pageLength.value,
	});
}

watch([customer, filters, pageLength], load, { immediate: true, deep: true });

const columns = computed(() =>
	isMobile.value
		? [
				{ label: "Order", key: "name", width: "minmax(140px, 2fr)" },
				{ label: "Status", key: "status", width: "150px" },
		  ]
		: [
				{ label: "Order", key: "name", width: "minmax(130px, 1.4fr)" },
				{ label: "Your PO", key: "po_no", width: "minmax(100px, 1fr)" },
				{ label: "Ordered", key: "transaction_date", width: "minmax(90px, 1fr)" },
				{ label: "Delivery by", key: "delivery_date", width: "minmax(90px, 1fr)" },
				{ label: "Value", key: "grand_total", width: "minmax(100px, 1fr)" },
				{ label: "Delivered", key: "delivered", width: "90px" },
				{ label: "Status", key: "status", width: "160px" },
		  ]
);

const options = {
	selectable: false,
	showTooltip: false,
	rowHeight: 48,
	getRowRoute: (row: SalesOrderRow) => ({
		name: row.status === "Draft" ? "SalesOrderEdit" : "SalesOrderDetail",
		params: { name: row.name },
	}),
};

function loadMore() {
	pageLength.value += 20;
}
</script>

<template>
	<PageContainer :look="LOOKS.salesOrder" wide title="Sales Orders">
		<template #actions>
			<Button
				v-if="customer"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="salesOrderList.loading"
				@click="load"
			/>
			<Button
				v-if="customer && canOrder"
				variant="solid"
				icon-left="lucide-plus"
				label="New order"
				:route="{ name: 'SalesOrderNew' }"
			/>
		</template>

		<EmptyState
			v-if="!customer"
			icon="lucide-store"
			title="Switch to a customer account"
			description="Orders belong to your customer accounts. Pick one at the top of the sidebar."
		/>

		<template v-else>
			<ListFilters
				v-model="filters"
				class="mb-4"
				:fields="[]"
				search-placeholder="Search by order or PO number"
			/>

			<div v-if="salesOrderList.loading && !page" class="flex justify-center py-16">
				<Spinner class="size-5" />
			</div>

			<EmptyState
				v-else-if="!rows.length && filters.search"
				icon="lucide-search-x"
				title="No order matches that number"
				description="Check the number, or clear the search to see every order."
			>
				<Button variant="subtle" label="Clear search" @click="filters = {}" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length"
				icon="lucide-shopping-cart"
				title="No orders yet"
				:description="
					canOrder
						? `Place an order for ${portal.activeParty?.title} and follow it here until it is delivered.`
						: `Orders from ${portal.activeParty?.title} appear here once we confirm them.`
				"
			>
				<Button
					v-if="canOrder"
					variant="solid"
					icon-left="lucide-plus"
					label="Place an order"
					:route="{ name: 'SalesOrderNew' }"
				/>
			</EmptyState>

			<template v-else>
				<ListView row-key="name" :columns="columns" :rows="rows" :options="options">
					<template #cell="{ column, row }">
						<span v-if="column.key === 'name'" class="flex min-w-0 flex-col">
							<span class="truncate text-base text-ink-gray-8">{{ row.name }}</span>
							<span v-if="isMobile" class="truncate text-xs text-ink-gray-5">
								{{ money(row.grand_total, row.currency) }}
								<template v-if="!row.is_draft">
									· {{ row.delivered }}% delivered</template
								>
							</span>
						</span>

						<span
							v-else-if="column.key === 'po_no'"
							class="truncate text-base text-ink-gray-7"
						>
							{{ row.po_no || "—" }}
						</span>

						<span
							v-else-if="column.key === 'transaction_date'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row.transaction_date) }}
						</span>

						<span
							v-else-if="column.key === 'delivery_date'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row.delivery_date) }}
						</span>

						<span
							v-else-if="column.key === 'grand_total'"
							class="text-base text-ink-gray-7"
						>
							{{ money(row.grand_total, row.currency) }}
						</span>

						<span
							v-else-if="column.key === 'delivered'"
							class="text-base text-ink-gray-7"
						>
							{{ row.is_draft ? "—" : `${row.delivered}%` }}
						</span>

						<Badge
							v-else
							:theme="SALES_ORDER_STATUS_THEME[row.status] || 'gray'"
							variant="subtle"
							:label="row.status"
						/>
					</template>
				</ListView>

				<div class="mt-3 flex flex-wrap items-center justify-between gap-2">
					<TabButtons
						v-model="pageLength"
						:options="
							[20, 50, 100].map((size) => ({ label: String(size), value: size }))
						"
					/>

					<div class="flex items-center gap-3">
						<Button
							v-if="rows.length < (page?.total ?? 0)"
							variant="subtle"
							label="Load more"
							:loading="salesOrderList.loading"
							@click="loadMore"
						/>
						<span class="text-base text-ink-gray-5">
							{{ rows.length }} of {{ page?.total ?? 0 }}
						</span>
					</div>
				</div>
			</template>
		</template>
	</PageContainer>
</template>
