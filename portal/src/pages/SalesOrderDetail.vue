<script setup lang="ts">
import { computed, watch } from "vue";
import { useRouter } from "vue-router";
import { Badge, Button, Spinner } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import RichText from "@/components/RichText.vue";
import PrintButton from "@/components/PrintButton.vue";
import { money, shortDate } from "@/data/purchase";
import {
	DELIVERY_NOTE_STATUS_THEME,
	SALES_ORDER_STATUS_THEME,
	createSalesOrderResource,
} from "@/data/selling";
import type { SalesOrder } from "@/data/selling";
import { usePortalStore } from "@/stores/portal";
import { ACCENTS, LOOKS } from "@/data/accents";

const props = defineProps<{ name: string }>();

const portal = usePortalStore();
const router = useRouter();

const request = createSalesOrderResource();

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const order = computed<SalesOrder | null>(() => request.data ?? null);

function load() {
	if (!customer.value) return;
	request.fetch({ name: props.name, customer: customer.value });
}

watch([customer, () => props.name], load, { immediate: true });
</script>

<template>
	<PageContainer
		:look="LOOKS.salesOrder"
		:title="order?.name || name"
		:copy="order?.name"
		:breadcrumbs="[
			{ label: 'Sales Orders', route: { name: 'SalesOrderList' } },
			{ label: order?.name || name },
		]"
	>
		<template #actions>
			<Badge
				v-if="order"
				:theme="SALES_ORDER_STATUS_THEME[order.status] || 'gray'"
				variant="subtle"
				:label="order.status"
			/>
			<PrintButton v-if="order" doctype="Sales Order" :name="order.name" :label="'order'" />
			<Button
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="request.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!customer"
			icon="lucide-store"
			title="Switch to a customer account"
			description="This order belongs to one of your customer accounts. Pick it at the top of the sidebar."
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
				@click="router.push({ name: 'SalesOrderList' })"
			/>
		</EmptyState>

		<div v-else-if="order" class="space-y-6">
			<dl
				:class="ACCENTS[LOOKS.salesOrder.accent].panel"
				class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-4"
			>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Ordered</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ shortDate(order.transaction_date) }}
					</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Delivery by</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ shortDate(order.delivery_date) }}
					</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Delivered</dt>
					<dd class="text-p-base text-ink-gray-8">{{ order.delivered }}%</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Invoiced</dt>
					<dd class="text-p-base text-ink-gray-8">{{ order.billed }}%</dd>
				</div>
			</dl>

			<div
				v-if="order.quotations.length || order.invoices.length"
				class="flex flex-wrap items-center gap-2"
			>
				<template v-if="order.quotations.length">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5">From</span>
					<Button
						v-for="quotation in order.quotations"
						:key="quotation"
						variant="subtle"
						:label="quotation"
						:route="{ name: 'QuotationDetail', params: { name: quotation } }"
					/>
				</template>
				<template v-if="order.invoices.length">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5"
						>Invoiced on</span
					>
					<Button
						v-for="invoice in order.invoices"
						:key="invoice"
						variant="subtle"
						:label="invoice"
						:route="{ name: 'SalesInvoiceDetail', params: { name: invoice } }"
					/>
				</template>
			</div>

			<div class="overflow-hidden rounded-6 border">
				<div
					class="hidden bg-surface-gray-1 px-4 py-2 text-xs uppercase tracking-wide text-ink-gray-5 sm:grid sm:grid-cols-12 sm:gap-3"
				>
					<span class="sm:col-span-4">Item</span>
					<span class="sm:col-span-2">Ordered</span>
					<span class="sm:col-span-2">Delivered</span>
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
							{{ item.delivered_qty }}
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

			<div class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Deliveries</p>

				<p v-if="!order.deliveries.length" class="mt-1 text-p-sm text-ink-gray-5">
					Nothing has been dispatched against this order yet.
				</p>

				<div v-else class="mt-2 divide-y">
					<RouterLink
						v-for="delivery in order.deliveries"
						:key="delivery.name"
						:to="{ name: 'DeliveryNoteDetail', params: { name: delivery.name } }"
						class="flex items-center justify-between gap-2 py-2 hover:bg-surface-gray-1"
					>
						<span class="text-p-base text-ink-gray-8">{{ delivery.name }}</span>
						<span class="flex items-center gap-2">
							<span class="text-p-sm text-ink-gray-5">
								{{ shortDate(delivery.posting_date) }}
							</span>
							<Badge
								:theme="DELIVERY_NOTE_STATUS_THEME[delivery.status] || 'gray'"
								variant="subtle"
								:label="delivery.status"
							/>
						</span>
					</RouterLink>
				</div>
			</div>

			<div v-if="order.shipping_address" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Ship to</p>
				<RichText class="mt-1" :html="order.shipping_address" />
			</div>

			<div v-if="order.terms" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Terms</p>
				<RichText class="mt-1" :html="order.terms" />
			</div>
		</div>
	</PageContainer>
</template>
