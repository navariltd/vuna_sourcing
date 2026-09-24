<script setup lang="ts">
import { computed, watch } from "vue";
import { useRouter } from "vue-router";
import { Badge, Button, Spinner } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import RichText from "@/components/RichText.vue";
import {
	SUPPLIER_QUOTATION_STATUS_THEME,
	createSupplierQuotationResource,
} from "@/data/supplierQuotation";
import type { SupplierQuotation } from "@/data/supplierQuotation";
import { usePortalStore } from "@/stores/portal";

const props = defineProps<{ name: string }>();

const portal = usePortalStore();
const router = useRouter();

const request = createSupplierQuotationResource();

const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);

const quotation = computed<SupplierQuotation | null>(() => request.data ?? null);

function load() {
	if (!supplier.value) return;
	request.fetch({ name: props.name, supplier: supplier.value });
}

watch([supplier, () => props.name], load, { immediate: true });

function formatDate(value: string | null) {
	if (!value) return "—";
	return new Date(value).toLocaleDateString(undefined, {
		day: "numeric",
		month: "short",
		year: "numeric",
	});
}

function money(value: number | null | undefined) {
	if (value === null || value === undefined) return "—";
	const amount = value.toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
	return quotation.value?.currency ? `${quotation.value.currency} ${amount}` : amount;
}
</script>

<template>
	<PageContainer
		:title="quotation?.quotation_number || quotation?.name || name"
		:breadcrumbs="[
			{ label: 'Supplier Quotations', route: { name: 'SupplierQuotationList' } },
			{ label: quotation?.name || name },
		]"
	>
		<template #actions>
			<Badge
				v-if="quotation"
				:theme="SUPPLIER_QUOTATION_STATUS_THEME[quotation.status]"
				variant="subtle"
				:label="quotation.status"
			/>
			<Button
				v-if="quotation?.rfq"
				variant="subtle"
				label="View RFQ"
				:route="{ name: 'RfqDetail', params: { name: quotation.rfq } }"
			/>
		</template>

		<EmptyState
			v-if="!supplier"
			icon="lucide-truck"
			title="Switch to a supplier account"
			description="This quotation belongs to one of your supplier accounts. Pick it at the top of the sidebar."
		/>

		<div v-else-if="request.loading && !quotation" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="request.error"
			icon="lucide-file-x"
			title="We cannot show this quotation"
			description="It may belong to another of your accounts, or have been removed."
		>
			<Button
				variant="subtle"
				label="Back to quotations"
				@click="router.push({ name: 'SupplierQuotationList' })"
			/>
		</EmptyState>

		<div v-else-if="quotation" class="space-y-6">
			<dl class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-4">
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Quoted as</dt>
					<dd class="text-p-base text-ink-gray-8">{{ portal.activeParty?.title }}</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Against</dt>
					<dd class="text-p-base text-ink-gray-8">{{ quotation.rfq || "—" }}</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Sent</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ formatDate(quotation.transaction_date) }}
					</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Valid until</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ formatDate(quotation.valid_till) }}
					</dd>
				</div>
			</dl>

			<div class="overflow-hidden rounded-6 border">
				<div
					class="hidden bg-surface-gray-1 px-4 py-2 text-xs uppercase tracking-wide text-ink-gray-5 sm:grid sm:grid-cols-12 sm:gap-3"
				>
					<span class="sm:col-span-4">Item</span>
					<span class="sm:col-span-2">Quantity</span>
					<span class="sm:col-span-2">Your price</span>
					<span class="sm:col-span-2">Lead time</span>
					<span class="sm:col-span-2 text-right">Amount</span>
				</div>

				<div class="divide-y">
					<div
						v-for="item in quotation.items"
						:key="item.name"
						class="grid gap-1 px-4 py-3 sm:grid-cols-12 sm:items-center sm:gap-3"
					>
						<div class="sm:col-span-4">
							<p class="text-base font-medium text-ink-gray-8">
								{{ item.item_name || item.item_code }}
							</p>
							<p
								v-if="item.description"
								class="mt-0.5 line-clamp-2 text-p-sm text-ink-gray-5"
							>
								{{ item.description }}
							</p>
						</div>

						<p class="text-p-sm text-ink-gray-7 sm:col-span-2">
							{{ item.qty }} {{ item.uom }}
						</p>
						<p class="text-p-sm text-ink-gray-7 sm:col-span-2">
							{{ money(item.rate) }}
						</p>
						<p class="text-p-sm text-ink-gray-7 sm:col-span-2">
							{{ item.lead_time_days ? `${item.lead_time_days} days` : "—" }}
						</p>
						<p
							class="text-p-sm font-medium text-ink-gray-8 sm:col-span-2 sm:text-right"
						>
							{{ money(item.amount) }}
						</p>
					</div>
				</div>

				<div
					class="flex items-center justify-between border-t bg-surface-gray-1 px-4 py-2 text-base font-medium text-ink-gray-8"
				>
					<span>Total</span>
					<span>{{ money(quotation.grand_total ?? quotation.total) }}</span>
				</div>
			</div>

			<div v-if="quotation.terms" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Terms</p>
				<RichText class="mt-1" :html="quotation.terms" />
			</div>
		</div>
	</PageContainer>
</template>
