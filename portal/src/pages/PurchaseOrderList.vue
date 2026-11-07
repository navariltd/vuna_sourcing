<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, Spinner, TabButtons } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import ListFilters from "@/components/ListFilters.vue";
import { PURCHASE_ORDER_STATUS_THEME, money, purchaseOrderList, shortDate } from "@/data/purchase";
import type { PurchaseOrderRow, PurchasePage } from "@/data/purchase";
import { usePortalStore } from "@/stores/portal";
import { useIsMobile } from "@/composables/useViewport";
import { LOOKS } from "@/data/accents";

const portal = usePortalStore();
const isMobile = useIsMobile();

const filters = ref<Record<string, string>>({});
const pageLength = ref(20);

const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);

const page = computed<PurchasePage<PurchaseOrderRow> | null>(() => purchaseOrderList.data ?? null);
const rows = computed<PurchaseOrderRow[]>(() => page.value?.rows ?? []);

function load() {
	if (!supplier.value) {
		purchaseOrderList.reset();
		return;
	}

	purchaseOrderList.fetch({
		supplier: supplier.value,
		search: filters.value.search || null,
		start: 0,
		limit: pageLength.value,
	});
}

watch([supplier, filters, pageLength], load, { immediate: true, deep: true });

const columns = computed(() =>
	isMobile.value
		? [
				{ label: "Order", key: "name", width: "minmax(140px, 2fr)" },
				{ label: "Status", key: "status", width: "130px" },
		  ]
		: [
				{ label: "Order", key: "name", width: "minmax(180px, 1.6fr)" },
				{ label: "Ordered", key: "transaction_date", width: "minmax(90px, 1fr)" },
				{ label: "Needed by", key: "required_by", width: "minmax(90px, 1fr)" },
				{ label: "Value", key: "grand_total", width: "minmax(140px, 1fr)" },
				{ label: "Received", key: "received", width: "90px" },
				{ label: "Status", key: "status", width: "150px" },
		  ]
);

const options = {
	selectable: false,
	showTooltip: false,
	rowHeight: 48,
	getRowRoute: (row: { name: string }) => ({
		name: "PurchaseOrderDetail",
		params: { name: row.name },
	}),
};

function loadMore() {
	pageLength.value += 20;
}
</script>

<template>
	<PageContainer :look="LOOKS.purchaseOrder" fluid title="Purchase Orders">
		<template #actions>
			<Button
				v-if="supplier"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="purchaseOrderList.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!supplier"
			icon="lucide-truck"
			title="Switch to a supplier account"
			description="Orders belong to your supplier accounts. Pick one at the top of the sidebar."
		/>

		<template v-else>
			<ListFilters
				v-model="filters"
				class="mb-4"
				:fields="[]"
				search-placeholder="Search by order number"
			/>

			<div v-if="purchaseOrderList.loading && !page" class="flex justify-center py-16">
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
				icon="lucide-package"
				title="No orders yet"
				:description="`Purchase orders placed with ${portal.activeParty?.title} appear here.`"
			/>

			<template v-else>
				<ListView
					class="list-fill"
					row-key="name"
					:columns="columns"
					:rows="rows"
					:options="options"
				>
					<template #cell="{ column, row }">
						<span v-if="column.key === 'name'" class="flex min-w-0 flex-col">
							<span class="truncate text-base text-ink-gray-8">{{ row.name }}</span>
							<span v-if="isMobile" class="truncate text-xs text-ink-gray-5">
								{{ money(row.grand_total, row.currency) }} · needed by
								{{ shortDate(row.required_by) }}
							</span>
						</span>

						<span
							v-else-if="column.key === 'transaction_date'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row.transaction_date) }}
						</span>

						<span
							v-else-if="column.key === 'required_by'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row.required_by) }}
						</span>

						<span
							v-else-if="column.key === 'grand_total'"
							class="text-base text-ink-gray-7"
						>
							{{ money(row.grand_total, row.currency) }}
						</span>

						<span
							v-else-if="column.key === 'received'"
							class="text-base text-ink-gray-7"
						>
							{{ row.received }}%
						</span>

						<Badge
							v-else
							:theme="PURCHASE_ORDER_STATUS_THEME[row.status] || 'gray'"
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
							:loading="purchaseOrderList.loading"
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
