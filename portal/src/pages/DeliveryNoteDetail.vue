<script setup lang="ts">
import { computed, watch } from "vue";
import { useRouter } from "vue-router";
import { Badge, Button, Spinner } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import RichText from "@/components/RichText.vue";
import PrintButton from "@/components/PrintButton.vue";
import { money, shortDate } from "@/data/purchase";
import { DELIVERY_NOTE_STATUS_THEME, createDeliveryNoteResource } from "@/data/selling";
import type { DeliveryNote } from "@/data/selling";
import { usePortalStore } from "@/stores/portal";
import { ACCENTS, LOOKS } from "@/data/accents";

const props = defineProps<{ name: string }>();

const portal = usePortalStore();
const router = useRouter();

const request = createDeliveryNoteResource();

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const delivery = computed<DeliveryNote | null>(() => request.data ?? null);

const transport = computed(() => {
	const d = delivery.value;
	if (!d) return [];
	return [
		["Transporter", d.transporter_name],
		["Waybill", d.lr_no],
		["Waybill date", d.lr_date ? shortDate(d.lr_date) : null],
		["Vehicle", d.vehicle_no],
		["Driver", d.driver_name],
	].filter((row) => row[1]);
});

function load() {
	if (!customer.value) return;
	request.fetch({ name: props.name, customer: customer.value });
}

watch([customer, () => props.name], load, { immediate: true });
</script>

<template>
	<PageContainer
		:look="LOOKS.deliveryNote"
		:title="delivery?.name || name"
		:copy="delivery?.name"
		:breadcrumbs="[
			{ label: 'Delivery Notes', route: { name: 'DeliveryNoteList' } },
			{ label: delivery?.name || name },
		]"
	>
		<template #actions>
			<Badge
				v-if="delivery"
				:theme="DELIVERY_NOTE_STATUS_THEME[delivery.status] || 'gray'"
				variant="subtle"
				:label="delivery.status"
			/>
			<PrintButton
				v-if="delivery"
				doctype="Delivery Note"
				:name="delivery.name"
				:label="'delivery note'"
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
			v-if="!customer"
			icon="lucide-store"
			title="Switch to a customer account"
			description="This delivery belongs to one of your customer accounts. Pick it at the top of the sidebar."
		/>

		<div v-else-if="request.loading && !delivery" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="request.error"
			icon="lucide-file-x"
			title="We cannot show this delivery"
			description="It may belong to another of your accounts, or have been withdrawn."
		>
			<Button
				variant="subtle"
				label="Back to deliveries"
				@click="router.push({ name: 'DeliveryNoteList' })"
			/>
		</EmptyState>

		<div v-else-if="delivery" class="space-y-6">
			<dl
				:class="ACCENTS[LOOKS.deliveryNote.accent].panel"
				class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-4"
			>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Dispatched</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ shortDate(delivery.posting_date) }}
					</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Your PO</dt>
					<dd class="text-p-base text-ink-gray-8">{{ delivery.po_no || "—" }}</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Invoiced</dt>
					<dd class="text-p-base text-ink-gray-8">{{ delivery.billed }}%</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Value</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ money(delivery.grand_total, delivery.currency) }}
					</dd>
				</div>
			</dl>

			<div
				v-if="
					delivery.sales_orders.length ||
					delivery.invoices.length ||
					delivery.return_against
				"
				class="flex flex-wrap items-center gap-2"
			>
				<template v-if="delivery.return_against">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5">Returns</span>
					<Button
						variant="subtle"
						:label="delivery.return_against"
						:route="{
							name: 'DeliveryNoteDetail',
							params: { name: delivery.return_against },
						}"
					/>
				</template>
				<template v-if="delivery.sales_orders.length">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5">Against</span>
					<Button
						v-for="order in delivery.sales_orders"
						:key="order"
						variant="subtle"
						:label="order"
						:route="{ name: 'SalesOrderDetail', params: { name: order } }"
					/>
				</template>
				<template v-if="delivery.invoices.length">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5"
						>Invoiced on</span
					>
					<Button
						v-for="invoice in delivery.invoices"
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
					<span class="sm:col-span-6">Item</span>
					<span class="sm:col-span-2">Quantity</span>
					<span class="sm:col-span-2">Returned</span>
					<span class="sm:col-span-2 text-right">Amount</span>
				</div>

				<div class="divide-y">
					<div
						v-for="item in delivery.items"
						:key="item.name"
						class="grid gap-1 px-4 py-3 sm:grid-cols-12 sm:items-center sm:gap-3"
					>
						<div class="sm:col-span-6">
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
						<p
							class="text-p-sm sm:col-span-2"
							:class="item.returned_qty ? 'text-ink-amber-7' : 'text-ink-gray-5'"
						>
							{{ item.returned_qty }}
						</p>
						<p
							class="text-p-sm font-medium text-ink-gray-8 sm:col-span-2 sm:text-right"
						>
							{{ money(item.amount, delivery.currency) }}
						</p>
					</div>
				</div>

				<div
					class="flex items-center justify-between border-t bg-surface-gray-1 px-4 py-2 text-base font-medium text-ink-gray-8"
				>
					<span>Total</span>
					<span>{{ money(delivery.grand_total, delivery.currency) }}</span>
				</div>
			</div>

			<dl
				v-if="transport.length"
				class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-3"
			>
				<div v-for="row in transport" :key="row[0] as string">
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">{{ row[0] }}</dt>
					<dd class="text-p-base text-ink-gray-8">{{ row[1] }}</dd>
				</div>
			</dl>

			<div v-if="delivery.shipping_address" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Shipped to</p>
				<RichText class="mt-1" :html="delivery.shipping_address" />
			</div>

			<div v-if="delivery.terms" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Terms</p>
				<RichText class="mt-1" :html="delivery.terms" />
			</div>
		</div>
	</PageContainer>
</template>
