<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, Spinner, TabButtons } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import ListFilters from "@/components/ListFilters.vue";
import {
	PURCHASE_INVOICE_STATUS_THEME,
	money,
	purchaseInvoiceList,
	shortDate,
} from "@/data/purchase";
import type { PurchaseInvoiceRow, PurchasePage } from "@/data/purchase";
import { usePortalStore } from "@/stores/portal";
import { useIsMobile } from "@/composables/useViewport";

const portal = usePortalStore();
const isMobile = useIsMobile();

const filters = ref<Record<string, string>>({});
const pageLength = ref(20);

const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);

const page = computed<PurchasePage<PurchaseInvoiceRow> | null>(
	() => purchaseInvoiceList.data ?? null
);
const rows = computed<PurchaseInvoiceRow[]>(() => page.value?.rows ?? []);

function load() {
	if (!supplier.value) {
		purchaseInvoiceList.reset();
		return;
	}

	purchaseInvoiceList.fetch({
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
				{ label: "Invoice", key: "name", width: "minmax(140px, 2fr)" },
				{ label: "Status", key: "status", width: "120px" },
		  ]
		: [
				{ label: "Invoice", key: "name", width: "minmax(130px, 1.4fr)" },
				{ label: "Your number", key: "bill_no", width: "minmax(100px, 1fr)" },
				{ label: "Dated", key: "posting_date", width: "minmax(90px, 1fr)" },
				{ label: "Due", key: "due_date", width: "minmax(90px, 1fr)" },
				{ label: "Value", key: "grand_total", width: "minmax(100px, 1fr)" },
				{ label: "Status", key: "status", width: "130px" },
		  ]
);

const options = {
	selectable: false,
	showTooltip: false,
	rowHeight: 48,
	getRowRoute: (row: { name: string }) => ({
		name: "PurchaseInvoiceDetail",
		params: { name: row.name },
	}),
};

function loadMore() {
	pageLength.value += 20;
}
</script>

<template>
	<PageContainer
		wide
		title="Purchase Invoices"
		:subtitle="supplier ? 'Your invoices as we hold them.' : undefined"
	>
		<template #actions>
			<Button
				v-if="supplier"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="purchaseInvoiceList.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!supplier"
			icon="lucide-truck"
			title="Switch to a supplier account"
			description="Invoices belong to your supplier accounts. Pick one at the top of the sidebar."
		/>

		<template v-else>
			<ListFilters
				v-model="filters"
				class="mb-4"
				:fields="[]"
				search-placeholder="Search by invoice number"
			/>

			<div v-if="purchaseInvoiceList.loading && !page" class="flex justify-center py-16">
				<Spinner class="size-5" />
			</div>

			<EmptyState
				v-else-if="!rows.length && filters.search"
				icon="lucide-search-x"
				title="No invoice matches that number"
				description="Check the number, or clear the search to see every invoice."
			>
				<Button variant="subtle" label="Clear search" @click="filters = {}" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length"
				icon="lucide-receipt"
				title="No invoices yet"
				description="Once we record an invoice from you, it appears here with its payment status."
			/>

			<template v-else>
				<ListView row-key="name" :columns="columns" :rows="rows" :options="options">
					<template #cell="{ column, row }">
						<span v-if="column.key === 'name'" class="flex min-w-0 flex-col">
							<span class="truncate text-base text-ink-gray-8">{{ row.name }}</span>
							<span v-if="isMobile" class="truncate text-xs text-ink-gray-5">
								{{ money(row.grand_total, row.currency) }} · due
								{{ shortDate(row.due_date) }}
							</span>
						</span>

						<span
							v-else-if="column.key === 'bill_no'"
							class="truncate text-base text-ink-gray-7"
						>
							{{ row.bill_no || "—" }}
						</span>

						<span
							v-else-if="column.key === 'posting_date'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row.posting_date) }}
						</span>

						<span
							v-else-if="column.key === 'due_date'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row.due_date) }}
						</span>

						<span
							v-else-if="column.key === 'grand_total'"
							class="text-base text-ink-gray-7"
						>
							{{ money(row.grand_total, row.currency) }}
						</span>

						<Badge
							v-else
							:theme="PURCHASE_INVOICE_STATUS_THEME[row.status] || 'gray'"
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
							:loading="purchaseInvoiceList.loading"
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
