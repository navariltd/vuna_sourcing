<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Alert, Badge, Button, Spinner, TabButtons } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import FilterFields from "@/components/FilterFields.vue";
import type { StatusOption } from "@/components/FilterFields.vue";
import { money, shortDate } from "@/data/purchase";
import {
	CREDIT_REQUEST_EXPLAINER,
	CREDIT_REQUEST_STATUS_LABEL,
	CREDIT_REQUEST_STATUS_THEME,
	creditRequestList,
	statusLabel,
} from "@/data/creditRequests";
import type { CreditRequestPage, CreditRequestRow } from "@/data/creditRequests";
import { usePortalStore } from "@/stores/portal";
import { useIsMobile } from "@/composables/useViewport";
import { useBranchFilter, withBranchColumn } from "@/composables/useBranchFilter";
import { LOOKS } from "@/data/accents";

const portal = usePortalStore();
const isMobile = useIsMobile();

const filters = ref<Record<string, string>>({});
const { branchFilter, showBranch, branchTitle, clearBranches } = useBranchFilter();
const pageLength = ref(20);

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const page = computed<CreditRequestPage | null>(() => creditRequestList.data?.data ?? null);
const rows = computed<CreditRequestRow[]>(() => page.value?.rows ?? []);
const canRequest = computed(() => !!page.value?.can_request);

function load() {
	if (!customer.value) {
		creditRequestList.reset();
		return;
	}

	creditRequestList.fetch({
		customer: customer.value,
		branches: branchFilter.value,
		search: filters.value.search || null,
		status: filters.value.status || null,
		start: 0,
		limit: pageLength.value,
	});
}

watch([customer, branchFilter, filters, pageLength], load, {
	immediate: true,
	deep: true,
});

const statusOptions = computed<StatusOption[]>(() =>
	Object.entries(CREDIT_REQUEST_STATUS_LABEL).map(([value, label]) => ({
		label,
		value,
		count: page.value?.counts?.[value] ?? 0,
	}))
);

const baseColumns = computed(() => {
	if (isMobile.value) {
		return [
			{ label: "Request", key: "name", width: "minmax(140px, 2fr)" },
			{ label: "Status", key: "status", width: "120px" },
		];
	}
	return [
		{ label: "Request", key: "name", width: "minmax(180px, 1.6fr)" },
		{ label: "Invoice", key: "sales_invoice", width: "minmax(130px, 1.3fr)" },
		{ label: "Requested", key: "transaction_date", width: "minmax(90px, 1fr)" },
		{ label: "Reason", key: "reason", width: "minmax(120px, 1.3fr)" },
		{ label: "Reduction", key: "total_amount", width: "minmax(140px, 1fr)" },
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
		name: "CreditRequestDetail",
		params: { name: row.name },
	}),
};

function loadMore() {
	pageLength.value += 20;
}
</script>

<template>
	<PageContainer :look="LOOKS.creditRequest" fluid title="Credit Note Requests">
		<template #actions>
			<Button
				v-if="customer"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="creditRequestList.loading"
				@click="load"
			/>
			<Button
				v-if="customer && canRequest"
				variant="solid"
				icon-left="lucide-plus"
				label="New request"
				:route="{ name: 'CreditRequestNew' }"
			/>
		</template>

		<EmptyState
			v-if="!customer"
			icon="lucide-store"
			title="Switch to a customer account"
			description="Credit note requests belong to your customer accounts. Pick one at the top of the sidebar."
		/>

		<template v-else>
			<Alert
				class="mb-4"
				theme="blue"
				icon="lucide-info"
				:title="CREDIT_REQUEST_EXPLAINER.title"
				:description="CREDIT_REQUEST_EXPLAINER.description"
			/>

			<FilterFields
				v-model="filters"
				class="mb-4"
				:statuses="statusOptions"
				search-placeholder="Search by number"
			/>

			<div v-if="creditRequestList.loading && !page" class="flex justify-center py-16">
				<Spinner class="size-5" />
			</div>

			<EmptyState
				v-else-if="!rows.length && branchFilter && !filters.search && !filters.status"
				icon="lucide-map-pin-off"
				title="No credit requests for the branches you picked"
				description="Pick other branches, or show every branch you have access to."
			>
				<Button variant="subtle" label="Show all branches" @click="clearBranches" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length && (filters.search || filters.status)"
				icon="lucide-search-x"
				title="No request matches"
				description="Check the number, or clear the filters to see every request."
			>
				<Button variant="subtle" label="Clear filters" @click="filters = {}" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length"
				:icon="LOOKS.creditRequest.icon"
				title="No credit note requests yet"
				:description="
					canRequest
						? 'Charged more than agreed? Ask us to lower the price and follow the request here.'
						: 'Credit note requests you raise with us appear here.'
				"
			>
				<Button
					v-if="canRequest"
					variant="solid"
					icon-left="lucide-plus"
					label="Request a credit note"
					:route="{ name: 'CreditRequestNew' }"
				/>
			</EmptyState>

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
								{{ money(row.total_amount, row.currency) }} ·
								{{ row.sales_invoice }}
							</span>
						</span>

						<span
							v-else-if="column.key === 'sales_invoice' || column.key === 'reason'"
							class="truncate text-base text-ink-gray-7"
						>
							{{ row[column.key] || "—" }}
						</span>

						<span
							v-else-if="column.key === 'transaction_date'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row.transaction_date) }}
						</span>

						<span
							v-else-if="column.key === 'total_amount'"
							class="text-base text-ink-gray-7"
						>
							{{ money(row.total_amount, row.currency) }}
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
							:theme="CREDIT_REQUEST_STATUS_THEME[row.status] || 'gray'"
							variant="subtle"
							:label="statusLabel(row.status)"
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
							:loading="creditRequestList.loading"
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
