<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, Spinner, TabButtons } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import ListFilters from "@/components/ListFilters.vue";
import { SUPPLIER_QUOTATION_STATUS_THEME, supplierQuotationList } from "@/data/supplierQuotation";
import type {
	SupplierQuotationPage,
	SupplierQuotationRow,
	SupplierQuotationStatus,
} from "@/data/supplierQuotation";
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

const page = computed<SupplierQuotationPage | null>(() => supplierQuotationList.data ?? null);
const rows = computed<SupplierQuotationRow[]>(() => page.value?.rows ?? []);

function load() {
	if (!supplier.value) {
		supplierQuotationList.reset();
		return;
	}

	supplierQuotationList.fetch({
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
				{ label: "Quotation", key: "name", width: "minmax(140px, 2fr)" },
				{ label: "Status", key: "status", width: "120px" },
		  ]
		: [
				{ label: "Quotation", key: "name", width: "minmax(110px, 1.4fr)" },
				{ label: "Against", key: "rfq", width: "minmax(110px, 1.2fr)" },
				{ label: "Value", key: "total", width: "minmax(90px, 1fr)" },
				{ label: "Valid until", key: "valid_till", width: "minmax(90px, 1fr)" },
				{ label: "Status", key: "status", width: "140px" },
		  ]
);

const options = {
	selectable: false,
	showTooltip: false,
	rowHeight: 48,
	getRowRoute: (row: SupplierQuotationRow) => ({
		name: "SupplierQuotationDetail",
		params: { name: row.name },
	}),
};

function formatDate(value: string | null) {
	if (!value) return "—";
	return new Date(value).toLocaleDateString(undefined, {
		day: "numeric",
		month: "short",
		year: "numeric",
	});
}

function money(row: SupplierQuotationRow) {
	if (row.total === null || row.total === undefined) return "—";
	const amount = row.total.toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
	return row.currency ? `${row.currency} ${amount}` : amount;
}

function loadMore() {
	pageLength.value += 20;
}
</script>

<template>
	<PageContainer :look="LOOKS.supplierQuotation" wide title="Supplier Quotations">
		<template #actions>
			<Button
				v-if="supplier"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="supplierQuotationList.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!supplier"
			icon="lucide-truck"
			title="Switch to a supplier account"
			description="Quotations belong to your supplier accounts. Pick one at the top of the sidebar."
		/>

		<template v-else>
			<ListFilters
				v-model="filters"
				class="mb-4"
				:fields="[]"
				search-placeholder="Search by quotation number"
			/>

			<div v-if="supplierQuotationList.loading && !page" class="flex justify-center py-16">
				<Spinner class="size-5" />
			</div>

			<EmptyState
				v-else-if="!rows.length && filters.search"
				icon="lucide-search-x"
				title="No quotation matches that number"
				description="Check the number, or clear the search to see everything you have sent."
			>
				<Button variant="subtle" label="Clear search" @click="filters = {}" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length"
				icon="lucide-file-check"
				title="You have not sent a quotation yet"
				description="Quotations appear here once you answer a request for quotation."
			>
				<Button variant="subtle" label="See open requests" :route="{ name: 'RfqList' }" />
			</EmptyState>

			<template v-else>
				<ListView row-key="name" :columns="columns" :rows="rows" :options="options">
					<template #cell="{ column, row }">
						<span v-if="column.key === 'name'" class="flex min-w-0 flex-col">
							<span class="truncate text-base text-ink-gray-8">
								{{ row.quotation_number || row.name }}
							</span>
							<span v-if="isMobile" class="truncate text-xs text-ink-gray-5">
								{{ money(row) }} · {{ formatDate(row.transaction_date) }}
							</span>
						</span>

						<span
							v-else-if="column.key === 'rfq'"
							class="truncate text-base text-ink-gray-7"
						>
							{{ row.rfq || "—" }}
						</span>

						<span v-else-if="column.key === 'total'" class="text-base text-ink-gray-7">
							{{ money(row) }}
						</span>

						<span
							v-else-if="column.key === 'valid_till'"
							class="text-base text-ink-gray-7"
						>
							{{ formatDate(row.valid_till) }}
						</span>

						<Badge
							v-else
							:theme="SUPPLIER_QUOTATION_STATUS_THEME[row.status as SupplierQuotationStatus]"
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
							:loading="supplierQuotationList.loading"
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
