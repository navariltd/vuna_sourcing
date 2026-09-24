<script setup lang="ts">
import { computed, watch } from "vue";
import { useRouter } from "vue-router";
import { Badge, Button, Spinner } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import RichText from "@/components/RichText.vue";
import {
	PURCHASE_ORDER_STATUS_THEME,
	createPurchaseOrderResource,
	money,
	shortDate,
} from "@/data/purchase";
import type { PurchaseOrder } from "@/data/purchase";
import { usePortalStore } from "@/stores/portal";

const props = defineProps<{ name: string }>();

const portal = usePortalStore();
const router = useRouter();

const request = createPurchaseOrderResource();

const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);

const order = computed<PurchaseOrder | null>(() => request.data ?? null);

function load() {
	if (!supplier.value) return;
	request.fetch({ name: props.name, supplier: supplier.value });
}

watch([supplier, () => props.name], load, { immediate: true });
</script>

<template>
	<PageContainer
		:title="order?.name || name"
		:breadcrumbs="[
			{ label: 'Purchase Orders', route: { name: 'PurchaseOrderList' } },
			{ label: order?.name || name },
		]"
	>
		<template #actions>
			<Badge
				v-if="order"
				:theme="PURCHASE_ORDER_STATUS_THEME[order.status] || 'gray'"
				variant="subtle"
				:label="order.status"
			/>
			<Button
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="request.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!supplier"
			icon="lucide-truck"
			title="Switch to a supplier account"
			description="This order belongs to one of your supplier accounts. Pick it at the top of the sidebar."
		/>

		<div v-else-if="request.loading && !order" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="request.error"
			icon="lucide-file-x"
			title="We cannot show this order"
			description="It may belong to another of your accounts, or have been withdrawn."
		>
			<Button
				variant="subtle"
				label="Back to orders"
				@click="router.push({ name: 'PurchaseOrderList' })"
			/>
		</EmptyState>

		<div v-else-if="order" class="space-y-6">
			<dl class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-4">
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Ordered</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ shortDate(order.transaction_date) }}
					</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Needed by</dt>
					<dd class="text-p-base text-ink-gray-8">{{ shortDate(order.required_by) }}</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Received</dt>
					<dd class="text-p-base text-ink-gray-8">{{ order.received }}%</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Value</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ money(order.grand_total, order.currency) }}
					</dd>
				</div>
			</dl>

			<div class="overflow-hidden rounded-6 border">
				<div
					class="hidden bg-surface-gray-1 px-4 py-2 text-xs uppercase tracking-wide text-ink-gray-5 sm:grid sm:grid-cols-12 sm:gap-3"
				>
					<span class="sm:col-span-4">Item</span>
					<span class="sm:col-span-2">Ordered</span>
					<span class="sm:col-span-2">Received</span>
					<span class="sm:col-span-2">Still to come</span>
					<span class="sm:col-span-2 text-right">Amount</span>
				</div>

				<div class="divide-y">
					<div
						v-for="item in order.items"
						:key="item.name"
						class="grid gap-1 px-4 py-3 sm:grid-cols-12 sm:items-center sm:gap-3"
					>
						<div class="sm:col-span-4">
							<p class="text-base font-medium text-ink-gray-8">
								{{ item.item_name }}
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
							{{ item.received_qty }}
						</p>
						<p
							class="text-p-sm sm:col-span-2"
							:class="item.outstanding_qty ? 'text-ink-amber-7' : 'text-ink-gray-5'"
						>
							{{ item.outstanding_qty }}
						</p>
						<p
							class="text-p-sm font-medium text-ink-gray-8 sm:col-span-2 sm:text-right"
						>
							{{ money(item.amount, order.currency) }}
						</p>
					</div>
				</div>

				<div
					class="flex items-center justify-between border-t bg-surface-gray-1 px-4 py-2 text-base font-medium text-ink-gray-8"
				>
					<span>Total</span>
					<span>{{ money(order.grand_total, order.currency) }}</span>
				</div>
			</div>

			<div v-if="order.receipts.length" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">
					What we have received
				</p>
				<div class="mt-2 divide-y">
					<div
						v-for="receipt in order.receipts"
						:key="receipt.name"
						class="flex items-center justify-between py-2"
					>
						<span class="text-p-base text-ink-gray-8">{{ receipt.name }}</span>
						<span class="text-p-sm text-ink-gray-5">
							{{ shortDate(receipt.posting_date) }} · {{ receipt.status }}
						</span>
					</div>
				</div>
			</div>

			<div v-if="order.terms" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Terms</p>
				<RichText class="mt-1" :html="order.terms" />
			</div>
		</div>
	</PageContainer>
</template>
