<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, Spinner, TabButtons } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import ListFilters from "@/components/ListFilters.vue";
import { money, shortDate } from "@/data/purchase";
import type { PurchasePage } from "@/data/purchase";
import { DELIVERY_NOTE_STATUS_THEME, deliveryNoteList } from "@/data/selling";
import type { DeliveryNoteRow } from "@/data/selling";
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

const page = computed<PurchasePage<DeliveryNoteRow> | null>(() => deliveryNoteList.data ?? null);
const rows = computed<DeliveryNoteRow[]>(() => page.value?.rows ?? []);

function load() {
	if (!customer.value) {
		deliveryNoteList.reset();
		return;
	}

	deliveryNoteList.fetch({
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
				{ label: "Delivery", key: "name", width: "minmax(140px, 2fr)" },
				{ label: "Status", key: "status", width: "130px" },
		  ]
		: [
				{ label: "Delivery", key: "name", width: "minmax(130px, 1.4fr)" },
				{ label: "Your PO", key: "po_no", width: "minmax(100px, 1fr)" },
				{ label: "Dispatched", key: "posting_date", width: "minmax(90px, 1fr)" },
				{ label: "Transporter", key: "transporter_name", width: "minmax(120px, 1.2fr)" },
				{ label: "Value", key: "grand_total", width: "minmax(100px, 1fr)" },
				{ label: "Status", key: "status", width: "140px" },
		  ]
);

const options = {
	selectable: false,
	showTooltip: false,
	rowHeight: 48,
	getRowRoute: (row: { name: string }) => ({
		name: "DeliveryNoteDetail",
		params: { name: row.name },
	}),
};

function loadMore() {
	pageLength.value += 20;
}
</script>

<template>
	<PageContainer :look="LOOKS.deliveryNote" wide title="Delivery Notes">
		<template #actions>
			<Button
				v-if="customer"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="deliveryNoteList.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!customer"
			icon="lucide-store"
			title="Switch to a customer account"
			description="Deliveries belong to your customer accounts. Pick one at the top of the sidebar."
		/>

		<template v-else>
			<ListFilters
				v-model="filters"
				class="mb-4"
				:fields="[]"
				search-placeholder="Search by delivery, PO or waybill number"
			/>

			<div v-if="deliveryNoteList.loading && !page" class="flex justify-center py-16">
				<Spinner class="size-5" />
			</div>

			<EmptyState
				v-else-if="!rows.length && filters.search"
				icon="lucide-search-x"
				title="No delivery matches that number"
				description="Check the number, or clear the search to see every delivery."
			>
				<Button variant="subtle" label="Clear search" @click="filters = {}" />
			</EmptyState>

			<EmptyState
				v-else-if="!rows.length"
				icon="lucide-truck"
				title="No deliveries yet"
				:description="`Goods we dispatch to ${portal.activeParty?.title} appear here.`"
			/>

			<template v-else>
				<ListView row-key="name" :columns="columns" :rows="rows" :options="options">
					<template #cell="{ column, row }">
						<span v-if="column.key === 'name'" class="flex min-w-0 flex-col">
							<span class="truncate text-base text-ink-gray-8">{{ row.name }}</span>
							<span v-if="isMobile" class="truncate text-xs text-ink-gray-5">
								{{ shortDate(row.posting_date) }}
								<template v-if="row.transporter_name">
									· {{ row.transporter_name }}
								</template>
							</span>
						</span>

						<span
							v-else-if="column.key === 'po_no'"
							class="truncate text-base text-ink-gray-7"
						>
							{{ row.po_no || "—" }}
						</span>

						<span
							v-else-if="column.key === 'posting_date'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row.posting_date) }}
						</span>

						<span
							v-else-if="column.key === 'transporter_name'"
							class="truncate text-base text-ink-gray-7"
						>
							{{ row.transporter_name || "—" }}
						</span>

						<span
							v-else-if="column.key === 'grand_total'"
							class="text-base text-ink-gray-7"
						>
							{{ money(row.grand_total, row.currency) }}
						</span>

						<Badge
							v-else
							:theme="DELIVERY_NOTE_STATUS_THEME[row.status] || 'gray'"
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
							:loading="deliveryNoteList.loading"
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
