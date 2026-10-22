<script setup lang="ts">
import { computed, watch } from "vue";
import { useRouter } from "vue-router";
import { Badge, Button, Spinner } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import RichText from "@/components/RichText.vue";
import ReturnNotes from "@/components/ReturnNotes.vue";
import PrintButton from "@/components/PrintButton.vue";
import { money, shortDate } from "@/data/purchase";
import { SALES_INVOICE_STATUS_THEME, createSalesInvoiceResource } from "@/data/selling";
import type { SalesInvoice } from "@/data/selling";
import { usePortalStore } from "@/stores/portal";
import { ACCENTS, LOOKS } from "@/data/accents";
import { CREDIT_REQUEST_STATUS_THEME, statusLabel } from "@/data/creditRequests";

const props = defineProps<{ name: string }>();

const portal = usePortalStore();
const router = useRouter();

const request = createSalesInvoiceResource();

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const invoice = computed<SalesInvoice | null>(() => request.data ?? null);

function load() {
	if (!customer.value) return;
	request.fetch({ name: props.name, customer: customer.value });
}

watch([customer, () => props.name], load, { immediate: true });
</script>

<template>
	<PageContainer
		:look="invoice?.is_return ? LOOKS.creditNote : LOOKS.salesInvoice"
		:title="invoice?.name || name"
		:copy="invoice?.name"
		:breadcrumbs="[
			invoice?.is_return
				? { label: 'Credit Notes', route: { name: 'CreditNoteList' } }
				: { label: 'Sales Invoices', route: { name: 'SalesInvoiceList' } },
			{ label: invoice?.name || name },
		]"
	>
		<template #actions>
			<Badge
				v-if="invoice"
				:theme="SALES_INVOICE_STATUS_THEME[invoice.status] || 'gray'"
				variant="subtle"
				:label="invoice.status"
			/>
			<PrintButton
				v-if="invoice"
				doctype="Sales Invoice"
				:name="invoice.name"
				:label="invoice.is_return ? 'credit note' : 'invoice'"
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
			description="This invoice belongs to one of your customer accounts. Pick it at the top of the sidebar."
		/>

		<div v-else-if="request.loading && !invoice" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="request.error"
			icon="lucide-file-x"
			title="We cannot show this invoice"
			description="It may belong to another of your accounts, or have been withdrawn."
		>
			<Button
				variant="subtle"
				label="Back to invoices"
				@click="router.push({ name: 'SalesInvoiceList' })"
			/>
		</EmptyState>

		<div v-else-if="invoice" class="space-y-6">
			<dl
				:class="
					ACCENTS[(invoice?.is_return ? LOOKS.creditNote : LOOKS.salesInvoice).accent]
						.panel
				"
				class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-4"
			>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Your PO</dt>
					<dd class="text-p-base text-ink-gray-8">{{ invoice.po_no || "—" }}</dd>
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
				v-if="invoice.credit_request?.open_request"
				class="flex flex-wrap items-center justify-between gap-3 rounded-6 border p-4"
			>
				<div class="flex min-w-0 flex-wrap items-center gap-2">
					<span class="text-base text-ink-gray-8">
						Credit note request {{ invoice.credit_request.open_request.name }}
					</span>
					<Badge
						:theme="
							CREDIT_REQUEST_STATUS_THEME[
								invoice.credit_request.open_request.request_status
							] || 'gray'
						"
						variant="subtle"
						:label="statusLabel(invoice.credit_request.open_request.request_status)"
					/>
				</div>
				<Button
					variant="subtle"
					label="View request"
					:route="{
						name: 'CreditRequestDetail',
						params: { name: invoice.credit_request.open_request.name },
					}"
				/>
			</div>

			<div
				v-else-if="invoice.credit_request?.can_request"
				class="flex flex-wrap items-center justify-between gap-3 rounded-6 border border-dashed p-4"
			>
				<div class="min-w-0">
					<p class="text-base font-medium text-ink-gray-8">
						Something wrong with this invoice?
					</p>
					<p class="mt-0.5 text-p-sm text-ink-gray-5">
						Ask us to credit damaged, wrong or missing items.
					</p>
				</div>
				<Button
					variant="solid"
					:icon-left="LOOKS.creditRequest.icon"
					label="Request a credit note"
					:route="{ name: 'CreditRequestNew', query: { invoice: invoice.name } }"
				/>
			</div>

			<div
				v-if="
					invoice.sales_orders.length ||
					invoice.delivery_notes.length ||
					invoice.return_against
				"
				class="flex flex-wrap items-center gap-2"
			>
				<template v-if="invoice.return_against">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5">Credits</span>
					<Button
						variant="subtle"
						:label="invoice.return_against"
						:route="{
							name: 'SalesInvoiceDetail',
							params: { name: invoice.return_against },
						}"
					/>
				</template>
				<template v-if="invoice.sales_orders.length">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5">Against</span>
					<Button
						v-for="order in invoice.sales_orders"
						:key="order"
						variant="subtle"
						:label="order"
						:route="{ name: 'SalesOrderDetail', params: { name: order } }"
					/>
				</template>
				<template v-if="invoice.delivery_notes.length">
					<span class="text-xs uppercase tracking-wide text-ink-gray-5"
						>Delivered on</span
					>
					<Button
						v-for="delivery in invoice.delivery_notes"
						:key="delivery"
						variant="subtle"
						:label="delivery"
						:route="{ name: 'DeliveryNoteDetail', params: { name: delivery } }"
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
					v-if="invoice.total_taxes"
					class="flex items-center justify-between border-t px-4 py-2 text-base text-ink-gray-7"
				>
					<span>Taxes and charges</span>
					<span>{{ money(invoice.total_taxes, invoice.currency) }}</span>
				</div>

				<div
					class="flex items-center justify-between border-t bg-surface-gray-1 px-4 py-2 text-base font-medium text-ink-gray-8"
				>
					<span>Total</span>
					<span>{{ money(invoice.grand_total, invoice.currency) }}</span>
				</div>
			</div>

			<ReturnNotes
				title="Credit notes against this invoice"
				:notes="invoice.credit_notes"
				:currency="invoice.currency"
				detail-route="SalesInvoiceDetail"
				:status-theme="SALES_INVOICE_STATUS_THEME"
			/>

			<div class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Payments</p>

				<p v-if="!invoice.payments.length" class="mt-1 text-p-sm text-ink-gray-5">
					No payment has been recorded against this invoice yet.
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
