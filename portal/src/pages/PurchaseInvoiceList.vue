<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, Spinner, TabButtons } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import ListFilters from "@/components/ListFilters.vue";
import {
	PURCHASE_INVOICE_STATUS_THEME,
	debitNoteList,
	money,
	purchaseInvoiceList,
	shortDate,
} from "@/data/purchase";
import type { PurchaseInvoiceRow, PurchasePage } from "@/data/purchase";
import { usePortalStore } from "@/stores/portal";
import { useIsMobile } from "@/composables/useViewport";
import { LOOKS } from "@/data/accents";

const props = defineProps<{ debitNotes?: boolean }>();

const portal = usePortalStore();
const isMobile = useIsMobile();

const list = props.debitNotes ? debitNoteList : purchaseInvoiceList;

const copy = props.debitNotes
	? {
			title: "Debit Notes",
			noun: "debit note",
			label: "Debit note",
			icon: "lucide-receipt-cent",
			search: "Search by debit note number",
			empty: "Debit notes we raise for returns or price corrections appear here.",
	  }
	: {
			title: "Purchase Invoices",
			noun: "invoice",
			label: "Invoice",
			icon: "lucide-receipt",
			search: "Search by invoice number",
			empty: "Once we record an invoice from you, it appears here with its payment status.",
	  };

const filters = ref<Record<string, string>>({});
const pageLength = ref(20);

const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);

const page = computed<PurchasePage<PurchaseInvoiceRow> | null>(() => list.data ?? null);
const rows = computed<PurchaseInvoiceRow[]>(() => page.value?.rows ?? []);

function load() {
	if (!supplier.value) {
		list.reset();
		return;
	}

	list.fetch({
		supplier: supplier.value,
		search: filters.value.search || null,
		debit_notes: props.debitNotes ? 1 : 0,
		start: 0,
		limit: pageLength.value,
	});
}

watch([supplier, filters, pageLength], load, { immediate: true, deep: true });

const columns = computed(() => {
	if (isMobile.value) {
		return [
			{ label: copy.label, key: "name", width: "minmax(140px, 2fr)" },
			{ label: "Status", key: "status", width: "120px" },
		];
	}
	if (props.debitNotes) {
		return [
			{ label: copy.label, key: "name", width: "minmax(130px, 1.4fr)" },
			{ label: "Against invoice", key: "return_against", width: "minmax(130px, 1.2fr)" },
			{ label: "Dated", key: "posting_date", width: "minmax(90px, 1fr)" },
			{ label: "Value", key: "grand_total", width: "minmax(100px, 1fr)" },
			{ label: "Status", key: "status", width: "130px" },
		];
	}
	return [
		{ label: copy.label, key: "name", width: "minmax(130px, 1.4fr)" },
		{ label: "Your number", key: "bill_no", width: "minmax(100px, 1fr)" },
		{ label: "Dated", key: "posting_date", width: "minmax(90px, 1fr)" },
		{ label: "Due", key: "due_date", width: "minmax(90px, 1fr)" },
		{ label: "Value", key: "grand_total", width: "minmax(100px, 1fr)" },
		{ label: "Status", key: "status", width: "130px" },
	];
});

const options = {
	selectable: false,
	showTooltip: false,
	rowHeight: 48,
	getRowRoute: (row: { name: string }) => ({
		name: "PurchaseInvoiceDetail",
		params: { name: row.name },
	}),
};

function mobileLine(row: PurchaseInvoiceRow) {
	if (props.debitNotes) {
		return `${money(row.grand_total, row.currency)} · against ${row.return_against || "—"}`;
	}
	return `${money(row.grand_total, row.currency)} · due ${shortDate(row.due_date)}`;
}

function loadMore() {
	pageLength.value += 20;
}
</script>

<template>
	<PageContainer
		:look="debitNotes ? LOOKS.debitNote : LOOKS.purchaseInvoice"
		wide
		:title="copy.title"
	>
		<template #actions>
			<Button
				v-if="supplier"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="list.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!supplier"
			icon="lucide-truck"
			title="Switch to a supplier account"
			:description="`${copy.title} belong to your supplier accounts. Pick one at the top of the sidebar.`"
		/>

		<template v-else>
			<ListFilters
				v-model="filters"
				class="mb-4"
				:fields="[]"
				:search-placeholder="copy.search"
			/>

			<div v-if="list.loading && !page" class="flex justify-center py-16">
				<Spinner class="size-5" />
			</div>

			<EmptyState
				v-else-if="!rows.length && filters.search"
				icon="lucide-search-x"
				:title="`No ${copy.noun} matches that number`"
				:description="`Check the number, or clear the search to see every ${copy.noun}.`"
			>
				<Button variant="subtle" label="Clear search" @click="filters = {}" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length"
				:icon="copy.icon"
				:title="`No ${copy.noun}s yet`"
				:description="copy.empty"
			/>

			<template v-else>
				<ListView row-key="name" :columns="columns" :rows="rows" :options="options">
					<template #cell="{ column, row }">
						<span v-if="column.key === 'name'" class="flex min-w-0 flex-col">
							<span class="truncate text-base text-ink-gray-8">{{ row.name }}</span>
							<span v-if="isMobile" class="truncate text-xs text-ink-gray-5">
								{{ mobileLine(row) }}
							</span>
						</span>

						<span
							v-else-if="column.key === 'bill_no' || column.key === 'return_against'"
							class="truncate text-base text-ink-gray-7"
						>
							{{ row[column.key] || "—" }}
						</span>

						<span
							v-else-if="column.key === 'posting_date' || column.key === 'due_date'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row[column.key]) }}
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
							:loading="list.loading"
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
