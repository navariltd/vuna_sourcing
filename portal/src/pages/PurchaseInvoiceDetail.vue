<script setup lang="ts">
import { computed, watch } from "vue";
import { useRouter } from "vue-router";
import { Badge, Button, Spinner } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import RichText from "@/components/RichText.vue";
import ReturnNotes from "@/components/ReturnNotes.vue";
import PrintButton from "@/components/PrintButton.vue";
import {
	PURCHASE_INVOICE_STATUS_THEME,
	createPurchaseInvoiceResource,
	money,
	shortDate,
} from "@/data/purchase";
import type { PurchaseInvoice } from "@/data/purchase";
import { usePortalStore } from "@/stores/portal";
import { ACCENTS, LOOKS } from "@/data/accents";

const props = defineProps<{ name: string }>();

const portal = usePortalStore();
const router = useRouter();

const request = createPurchaseInvoiceResource();

const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);

const invoice = computed<PurchaseInvoice | null>(() => request.data ?? null);

function load() {
	if (!supplier.value) return;
	request.fetch({ name: props.name, supplier: supplier.value });
}

watch([supplier, () => props.name], load, { immediate: true });
</script>

<template>
	<PageContainer
		:look="invoice?.is_return ? LOOKS.debitNote : LOOKS.purchaseInvoice"
		:title="invoice?.bill_no || invoice?.name || name"
		:copy="invoice?.name"
		:breadcrumbs="[
			invoice?.is_return
				? { label: 'Debit Notes', route: { name: 'DebitNoteList' } }
				: { label: 'Purchase Invoices', route: { name: 'PurchaseInvoiceList' } },
			{ label: invoice?.name || name },
		]"
	>
		<template #actions>
			<Badge
				v-if="invoice"
				:theme="PURCHASE_INVOICE_STATUS_THEME[invoice.status] || 'gray'"
				variant="subtle"
				:label="invoice.status"
			/>
			<PrintButton
				v-if="invoice"
				doctype="Purchase Invoice"
				:name="invoice.name"
				:label="invoice.is_return ? 'debit note' : 'invoice'"
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
			description="This invoice belongs to one of your supplier accounts. Pick it at the top of the sidebar."
		/>

		<div v-else-if="request.loading && !invoice" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="request.error"
			icon="lucide-file-x"
			title="We cannot show this invoice"
			description="It may belong to another of your accounts, or have been removed."
		>
			<Button
				variant="subtle"
				label="Back to invoices"
				@click="router.push({ name: 'PurchaseInvoiceList' })"
			/>
		</EmptyState>

		<div v-else-if="invoice" class="space-y-6">
			<div
				v-if="invoice.on_hold"
				class="flex items-start gap-2 rounded-6 border border-outline-amber-2 bg-surface-amber-1 p-4"
			>
				<i class="lucide-pause size-4 shrink-0 text-ink-amber-7" />
				<div>
					<p class="text-base font-medium text-ink-gray-8">Payment is on hold</p>
					<p class="mt-0.5 text-p-sm text-ink-gray-7">
						Reason for Holding:
						{{ invoice.hold_reason || "No reason was recorded" }}
					</p>
					<p v-if="invoice.release_date" class="mt-0.5 text-p-sm text-ink-gray-6">
						Due for release on {{ shortDate(invoice.release_date) }}
					</p>
				</div>
			</div>

			<dl
				:class="
					ACCENTS[(invoice?.is_return ? LOOKS.debitNote : LOOKS.purchaseInvoice).accent]
						.panel
				"
				class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-4"
			>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Our reference</dt>
					<dd class="text-p-base text-ink-gray-8">{{ invoice.name }}</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Dated</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ shortDate(invoice.posting_date) }}
					</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Due</dt>
					<dd class="text-p-base text-ink-gray-8">{{ shortDate(invoice.due_date) }}</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Outstanding</dt>
					<dd class="text-p-base font-medium text-ink-gray-8">
						{{ money(invoice.outstanding_amount, invoice.currency) }}
					</dd>
				</div>
			</dl>

			<div
				v-if="invoice.purchase_orders.length || invoice.return_against"
				class="flex flex-wrap items-center gap-2"
			>
				<template v-if="invoice.return_against">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5">Debits</span>
					<Button
						variant="subtle"
						:label="invoice.return_against"
						:route="{
							name: 'PurchaseInvoiceDetail',
							params: { name: invoice.return_against },
						}"
					/>
				</template>
				<template v-if="invoice.purchase_orders.length">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5">Against</span>
					<Button
						v-for="order in invoice.purchase_orders"
						:key="order"
						variant="subtle"
						:label="order"
						:route="{ name: 'PurchaseOrderDetail', params: { name: order } }"
					/>
				</template>
			</div>

			<div class="overflow-hidden rounded-6 border">
				<div
					class="hidden bg-surface-gray-1 px-4 py-2 text-xs uppercase tracking-wide text-ink-gray-5 sm:grid sm:grid-cols-12 sm:gap-3"
				>
					<span class="sm:col-span-6">Item</span>
					<span class="sm:col-span-2">Quantity</span>
					<span class="sm:col-span-2">Rate</span>
					<span class="sm:col-span-2 text-right">Amount</span>
				</div>

				<div class="divide-y">
					<div
						v-for="item in invoice.items"
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
						<p class="text-p-sm text-ink-gray-7 sm:col-span-2">
							{{ money(item.rate, invoice.currency) }}
						</p>
						<p
							class="text-p-sm font-medium text-ink-gray-8 sm:col-span-2 sm:text-right"
						>
							{{ money(item.amount, invoice.currency) }}
						</p>
					</div>
				</div>

				<div
					class="flex items-center justify-between border-t bg-surface-gray-1 px-4 py-2 text-base font-medium text-ink-gray-8"
				>
					<span>Total</span>
					<span>{{ money(invoice.grand_total, invoice.currency) }}</span>
				</div>
			</div>

			<ReturnNotes
				title="Debit notes against this invoice"
				:notes="invoice.debit_notes"
				:currency="invoice.currency"
				detail-route="PurchaseInvoiceDetail"
				:status-theme="PURCHASE_INVOICE_STATUS_THEME"
			/>

			<div class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Payments</p>

				<p v-if="!invoice.payments.length" class="mt-1 text-p-sm text-ink-gray-5">
					Nothing has been paid against this invoice yet.
				</p>

				<div v-else class="mt-2 divide-y">
					<div
						v-for="payment in invoice.payments"
						:key="payment.name"
						class="flex flex-wrap items-center justify-between gap-2 py-2"
					>
						<span class="text-p-base text-ink-gray-8">
							{{ shortDate(payment.posting_date) }}
							<span v-if="payment.mode_of_payment" class="text-ink-gray-5">
								· {{ payment.mode_of_payment }}
							</span>
							<span v-if="payment.reference_no" class="text-ink-gray-5">
								· {{ payment.reference_no }}
							</span>
						</span>
						<span class="text-p-base font-medium text-ink-gray-8">
							{{ money(payment.allocated_amount, invoice.currency) }}
						</span>
					</div>
				</div>
			</div>

			<div v-if="invoice.terms" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Terms</p>
				<RichText class="mt-1" :html="invoice.terms" />
			</div>
		</div>
	</PageContainer>
</template>
