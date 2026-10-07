<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, Spinner, TabButtons, Tooltip } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import ListFilters from "@/components/ListFilters.vue";
import { RFQ_STATUSES, RFQ_STATUS_HINT, RFQ_STATUS_THEME, rfqList, rfqRoute } from "@/data/rfq";
import type { RfqPage, RfqRow, RfqStatus } from "@/data/rfq";
import { usePortalStore } from "@/stores/portal";
import { useIsMobile } from "@/composables/useViewport";
import { LOOKS } from "@/data/accents";

const portal = usePortalStore();
const isMobile = useIsMobile();

const ALL = "All";

const filters = ref<Record<string, string>>({});
const status = ref<RfqStatus | typeof ALL>("Invited");
const pageLength = ref(20);

const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);

const page = computed<RfqPage | null>(() => rfqList.data ?? null);
const rows = computed<RfqRow[]>(() => page.value?.rows ?? []);
const counts = computed(() => page.value?.counts ?? {});
const everything = computed(() =>
	Object.values(counts.value).reduce((sum, count) => sum + count, 0)
);

const statusTabs = computed(() => [
	...RFQ_STATUSES.map((value) => ({
		label: `${value} (${counts.value[value] ?? 0})`,
		value,
	})),
	{ label: `${ALL} (${everything.value})`, value: ALL },
]);

function load() {
	if (!supplier.value) {
		rfqList.reset();
		return;
	}

	rfqList.fetch({
		supplier: supplier.value,
		status: status.value === ALL ? null : status.value,
		search: filters.value.search || null,
		start: 0,
		limit: pageLength.value,
	});
}

watch([supplier, filters, status, pageLength], load, { immediate: true, deep: true });

const columns = computed(() =>
	isMobile.value
		? [
				{ label: "Request", key: "name", width: "minmax(140px, 2fr)" },
				{ label: "Status", key: "status", width: "110px" },
		  ]
		: [
				{ label: "Request", key: "name", width: "minmax(160px, 2fr)" },
				{ label: "Items", key: "items", width: "80px" },
				{ label: "Bids close", key: "closes_at", width: "minmax(150px, 1fr)" },
				{ label: "Status", key: "status", width: "minmax(140px, 1fr)" },
		  ]
);

const options = {
	selectable: false,
	showTooltip: false,
	rowHeight: 48,
	getRowRoute: rfqRoute,
};

function formatDateTime(value: string | null) {
	if (!value) return "—";
	return new Date(value).toLocaleString(undefined, {
		day: "numeric",
		month: "short",
		year: "numeric",
		hour: "2-digit",
		minute: "2-digit",
		timeZoneName: "short",
	});
}

function loadMore() {
	pageLength.value += 20;
}
</script>

<template>
	<PageContainer :look="LOOKS.rfq" wide title="Request for Quotation">
		<template #actions>
			<Badge
				v-if="supplier && counts.Invited"
				theme="blue"
				variant="subtle"
				:label="`${counts.Invited} awaiting your prices`"
			/>
			<Badge
				v-if="supplier && counts.Bidding"
				theme="violet"
				variant="subtle"
				class="cursor-pointer"
				:label="`${counts.Bidding} live bid${counts.Bidding === 1 ? '' : 's'}`"
				@click="status = 'Bidding'"
			/>
			<Badge
				v-if="supplier && counts.Draft"
				theme="amber"
				variant="subtle"
				:label="`${counts.Draft} draft${counts.Draft === 1 ? '' : 's'} not sent`"
			/>
			<Button
				v-if="supplier"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="rfqList.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!supplier"
			icon="lucide-truck"
			title="Switch to a supplier account"
			description="Requests for quotation are sent to your supplier accounts. Pick one at the top of the sidebar."
		/>

		<template v-else>
			<ListFilters
				v-model="filters"
				class="mb-3"
				:fields="[]"
				search-placeholder="Search by request number"
			/>

			<div class="mb-4 overflow-x-auto">
				<TabButtons v-model="status" :options="statusTabs" />
			</div>

			<div v-if="rfqList.loading && !page" class="flex justify-center py-16">
				<Spinner class="size-5" />
			</div>

			<EmptyState
				v-else-if="!rows.length && filters.search"
				icon="lucide-search-x"
				title="No request matches that number"
				description="Check the number, or clear the search to see everything."
			>
				<Button variant="subtle" label="Clear search" @click="filters = {}" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length && status !== ALL"
				icon="lucide-inbox"
				:title="`No ${status.toLowerCase()} requests`"
				:description="RFQ_STATUS_HINT[status]"
			>
				<Button variant="subtle" label="Show all requests" @click="status = ALL" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length"
				icon="lucide-file-text"
				title="Nothing to quote yet"
				:description="`When ${portal.activeParty?.title} is invited to quote, the request appears here.`"
			/>

			<template v-else>
				<ListView row-key="name" :columns="columns" :rows="rows" :options="options">
					<template #cell="{ column, row }">
						<span v-if="column.key === 'name'" class="flex min-w-0 flex-col">
							<span class="truncate text-base text-ink-gray-8">{{ row.name }}</span>
							<span v-if="isMobile" class="truncate text-xs text-ink-gray-5">
								{{ row.items }} {{ row.items === 1 ? "item" : "items" }} · closes
								{{ formatDateTime(row.closes_at) }}
							</span>
						</span>

						<span v-else-if="column.key === 'items'" class="text-base text-ink-gray-7">
							{{ row.items }}
						</span>

						<span
							v-else-if="column.key === 'closes_at'"
							class="text-base text-ink-gray-7"
						>
							{{ formatDateTime(row.closes_at) }}
						</span>

						<Tooltip v-else :text="RFQ_STATUS_HINT[row.status as RfqStatus]">
							<Badge
								:theme="RFQ_STATUS_THEME[row.status as RfqStatus]"
								variant="subtle"
								:label="row.status"
							/>
						</Tooltip>
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
							:loading="rfqList.loading"
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
