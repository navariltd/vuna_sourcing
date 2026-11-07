<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, ErrorMessage, Spinner, TabButtons } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import FilterFields from "@/components/FilterFields.vue";
import { errorText } from "@/data/orders";
import type { StatusOption } from "@/components/FilterFields.vue";
import { money, shortDate } from "@/data/purchase";
import type { PurchasePage } from "@/data/purchase";
import { SALES_INVOICE_STATUS_THEME, creditNoteList, salesInvoiceList } from "@/data/selling";
import type { SalesInvoiceRow } from "@/data/selling";
import { usePortalStore } from "@/stores/portal";
import { useIsMobile } from "@/composables/useViewport";
import { useBranchFilter, withBranchColumn } from "@/composables/useBranchFilter";
import { LOOKS } from "@/data/accents";

const props = defineProps<{ creditNotes?: boolean }>();

const portal = usePortalStore();
const isMobile = useIsMobile();

const list = props.creditNotes ? creditNoteList : salesInvoiceList;

const copy = props.creditNotes
	? {
			title: "Credit Notes",
			noun: "credit note",
			label: "Credit note",
			icon: "lucide-receipt-cent",
			search: "Search by credit note or PO number",
			empty: "Credit notes we issue for returns or corrections appear here.",
	  }
	: {
			title: "Sales Invoices",
			noun: "invoice",
			label: "Invoice",
			icon: "lucide-receipt",
			search: "Search by invoice or PO number",
			empty: "Invoices we raise to you appear here with their payment status.",
	  };

const filters = ref<Record<string, string>>({});
const { branchFilter, showBranch, branchTitle, clearBranches } = useBranchFilter();
const pageLength = ref(20);

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const page = computed<PurchasePage<SalesInvoiceRow> | null>(() => list.data ?? null);
const rows = computed<SalesInvoiceRow[]>(() => page.value?.rows ?? []);

const STATUSES = props.creditNotes
	? ["Return", "Credit Note Issued"]
	: ["Unpaid", "Overdue", "Partly Paid", "Paid", "Credit Note Issued"];

const statusOptions = computed<StatusOption[]>(() => {
	const counts = page.value?.counts ?? {};
	return [...new Set([...STATUSES, ...Object.keys(counts)])].map((value) => ({
		label: value,
		value,
		count: counts[value] ?? 0,
	}));
});

const filtered = computed(
	() =>
		!!(
			filters.value.search ||
			filters.value.status ||
			filters.value.from_date ||
			filters.value.to_date
		)
);

function load() {
	if (!customer.value) {
		list.reset();
		return;
	}

	list.fetch({
		customer: customer.value,
		branches: branchFilter.value,
		search: filters.value.search || null,
		status: filters.value.status || null,
		from_date: filters.value.from_date || null,
		to_date: filters.value.to_date || null,
		credit_notes: props.creditNotes ? 1 : 0,
		start: 0,
		limit: pageLength.value,
	});
}

watch([customer, branchFilter, filters, pageLength], load, {
	immediate: true,
	deep: true,
});

const baseColumns = computed(() => {
	if (isMobile.value) {
		return [
			{ label: copy.label, key: "name", width: "minmax(140px, 2fr)" },
			{ label: "Status", key: "status", width: "120px" },
		];
	}
	if (props.creditNotes) {
		return [
			{ label: copy.label, key: "name", width: "minmax(180px, 1.6fr)" },
			{ label: "Against invoice", key: "return_against", width: "minmax(130px, 1.2fr)" },
			{ label: "Dated", key: "posting_date", width: "minmax(90px, 1fr)" },
			{ label: "Value", key: "grand_total", width: "minmax(140px, 1fr)" },
			{ label: "Status", key: "status", width: "130px" },
		];
	}
	return [
		{ label: copy.label, key: "name", width: "minmax(180px, 1.6fr)" },
		{ label: "Your PO", key: "po_no", width: "minmax(100px, 1fr)" },
		{ label: "Dated", key: "posting_date", width: "minmax(90px, 1fr)" },
		{ label: "Due", key: "due_date", width: "minmax(90px, 1fr)" },
		{ label: "Value", key: "grand_total", width: "minmax(140px, 1fr)" },
		{ label: "Outstanding", key: "outstanding_amount", width: "minmax(140px, 1fr)" },
		{ label: "Status", key: "status", width: "130px" },
	];
});

const columns = computed(() =>
	withBranchColumn(baseColumns.value, showBranch.value && !isMobile.value)
);

const options = {
	selectable: false,
	showTooltip: false,
	rowHeight: 48,
	getRowRoute: (row: { name: string }) => ({
		name: "SalesInvoiceDetail",
		params: { name: row.name },
	}),
};

function mobileLine(row: SalesInvoiceRow) {
	if (props.creditNotes) {
		return `${money(row.grand_total, row.currency)} · against ${row.return_against || "—"}`;
	}
	const prefix = row.is_debit_note ? "Debit note · " : "";
	return `${prefix}${money(row.outstanding_amount, row.currency)} to pay · due ${shortDate(
		row.due_date
	)}`;
}

function loadMore() {
	pageLength.value += 20;
}
</script>

<template>
	<PageContainer
		:look="creditNotes ? LOOKS.creditNote : LOOKS.salesInvoice"
		fluid
		:title="copy.title"
	>
		<template #actions>
			<Button
				v-if="customer"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="list.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!customer"
			icon="lucide-store"
			title="Switch to a customer account"
			:description="`${copy.title} belong to your customer accounts. Pick one at the top of the sidebar.`"
		/>

		<template v-else>
			<FilterFields
				v-model="filters"
				class="mb-4"
				:statuses="statusOptions"
				:dates="true"
				:search-placeholder="copy.search"
			/>

			<ErrorMessage
				v-if="list.error"
				class="mb-4"
				:message="
					errorText(list.error, 'We could not load your invoices. Please try again.')
				"
			/>

			<div v-if="list.loading && !page" class="flex justify-center py-16">
				<Spinner class="size-5" />
			</div>

			<EmptyState
				v-else-if="!rows.length && branchFilter && !filtered"
				icon="lucide-map-pin-off"
				:title="`No ${copy.noun}s for the branches you picked`"
				description="Pick other branches, or show every branch you have access to."
			>
				<Button variant="subtle" label="Show all branches" @click="clearBranches" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length && filtered"
				icon="lucide-search-x"
				:title="`No ${copy.noun} matches these filters`"
				:description="`Try another status or dates, or clear the filters to see every ${copy.noun}.`"
			>
				<Button variant="subtle" label="Clear filters" @click="filters = {}" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length"
				:icon="copy.icon"
				:title="`No ${copy.noun}s yet`"
				:description="copy.empty"
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
								{{ mobileLine(row) }}
							</span>
							<span
								v-else-if="row.is_debit_note"
								class="truncate text-xs text-ink-gray-5"
							>
								Debit note
							</span>
						</span>

						<span
							v-else-if="column.key === 'po_no' || column.key === 'return_against'"
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
							v-else-if="
								column.key === 'grand_total' || column.key === 'outstanding_amount'
							"
							class="text-base text-ink-gray-7"
						>
							{{ money(row[column.key], row.currency) }}
						</span>

						<span
							v-else-if="column.key === 'branch'"
							class="truncate text-base text-ink-gray-7"
							:title="branchTitle(row.branch)"
						>
							{{ branchTitle(row.branch) || "—" }}
						</span>

						<Badge
							v-else
							:theme="SALES_INVOICE_STATUS_THEME[row.status] || 'gray'"
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
