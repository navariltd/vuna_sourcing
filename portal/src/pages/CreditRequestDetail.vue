<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Badge, Button, Dialog, ErrorMessage, Spinner, toast } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import ReturnNotes from "@/components/ReturnNotes.vue";
import { money, shortDate } from "@/data/purchase";
import {
	CREDIT_REQUEST_STATUS_THEME,
	createCreditRequestResource,
	statusLabel,
	withdrawCreditRequest,
} from "@/data/creditRequests";
import type { CreditRequest } from "@/data/creditRequests";
import { SALES_INVOICE_STATUS_THEME } from "@/data/selling";
import { errorText } from "@/data/orders";
import { isOk } from "@/types/api";
import { usePortalStore } from "@/stores/portal";
import { ACCENTS, LOOKS } from "@/data/accents";
import type { Accent } from "@/data/accents";

const props = defineProps<{ name: string }>();

const portal = usePortalStore();
const router = useRouter();

const request = createCreditRequestResource();

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const credit = computed<CreditRequest | null>(() => request.data?.data ?? null);

function load() {
	if (!customer.value) return;
	request.fetch({ name: props.name, customer: customer.value });
}

watch([customer, () => props.name], load, { immediate: true });

interface Step {
	accent: Accent;
	title: string;
	text: string;
}

const step = computed<Step | null>(() => {
	const steps: Record<string, Step> = {
		"Pending Review": {
			accent: "purple",
			title: "We are reviewing your request",
			text: "Our accounts team checks every request. You can withdraw it until they decide.",
		},
		"Returned for Correction": {
			accent: "amber",
			title: "We need a few changes",
			text: "Change the request and send it back to us.",
		},
		Approved: {
			accent: "blue",
			title: "Approved",
			text: "We are preparing your credit note. It appears here as soon as it is issued.",
		},
		"Credit Note Issued": {
			accent: "green",
			title: "Credited",
			text: credit.value?.credit_note
				? `Credit note ${credit.value.credit_note.name} has been issued against the invoice.`
				: "Your credit note has been issued against the invoice.",
		},
		Rejected: {
			accent: "gray",
			title: "We could not approve this request",
			text: "Contact us if you would like to discuss it.",
		},
		Withdrawn: {
			accent: "gray",
			title: "You withdrew this request",
			text: "Raise a new request from the invoice if you still need a credit.",
		},
		Cancelled: {
			accent: "gray",
			title: "We cancelled this request",
			text: "Contact us if you have any questions, or raise a new request from the invoice.",
		},
	};
	return credit.value ? steps[credit.value.status] ?? null : null;
});

const confirmingWithdraw = ref(false);
const withdrawing = ref(false);
const withdrawError = ref<string | null>(null);

async function withdraw() {
	if (!credit.value || !customer.value) return;

	withdrawing.value = true;
	withdrawError.value = null;
	try {
		const response = await withdrawCreditRequest(customer.value, credit.value.name);
		if (!isOk(response)) {
			withdrawError.value = response.message || "We could not withdraw this request.";
			return;
		}
		confirmingWithdraw.value = false;
		toast.success(response.message || "Request withdrawn.");
		load();
	} catch (error) {
		withdrawError.value = errorText(error, "We could not withdraw this request.");
		load();
	} finally {
		withdrawing.value = false;
	}
}
</script>

<template>
	<PageContainer
		:look="LOOKS.creditRequest"
		:title="credit?.name || name"
		:copy="credit?.name"
		:breadcrumbs="[
			{ label: 'Credit Note Requests', route: { name: 'CreditRequestList' } },
			{ label: credit?.name || name },
		]"
	>
		<template #actions>
			<Badge
				v-if="credit"
				:theme="CREDIT_REQUEST_STATUS_THEME[credit.status] || 'gray'"
				variant="subtle"
				:label="statusLabel(credit.status)"
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
			description="This request belongs to one of your customer accounts. Pick it at the top of the sidebar."
		/>

		<div v-else-if="request.loading && !credit" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="request.error"
			icon="lucide-file-x"
			title="We cannot show this request"
			description="It may belong to another of your accounts."
		>
			<Button
				variant="subtle"
				label="Back to credit note requests"
				@click="router.push({ name: 'CreditRequestList' })"
			/>
		</EmptyState>

		<div v-else-if="credit" class="space-y-6">
			<div
				v-if="step"
				:class="ACCENTS[step.accent].panel"
				class="flex flex-wrap items-center justify-between gap-3 rounded-6 border p-4"
			>
				<div class="min-w-0">
					<p class="text-base font-medium text-ink-gray-8">{{ step.title }}</p>
					<p class="mt-1 text-p-sm text-ink-gray-6">{{ step.text }}</p>
					<p
						v-if="credit.review_remarks && credit.status !== 'Approved'"
						class="mt-2 whitespace-pre-line text-p-sm text-ink-gray-8"
					>
						<span class="font-medium">From our team:</span> {{ credit.review_remarks }}
					</p>
				</div>
				<div class="flex flex-wrap gap-2">
					<Button
						v-if="credit.editable"
						variant="solid"
						icon-left="lucide-pencil"
						label="Change and resubmit"
						:route="{ name: 'CreditRequestEdit', params: { name: credit.name } }"
					/>
					<Button
						v-if="credit.withdrawable"
						variant="subtle"
						theme="red"
						icon-left="lucide-undo-2"
						label="Withdraw"
						@click="confirmingWithdraw = true"
					/>
				</div>
			</div>

			<ErrorMessage v-if="withdrawError" :message="withdrawError" />

			<dl
				:class="ACCENTS[LOOKS.creditRequest.accent].panel"
				class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-4"
			>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Invoice</dt>
					<dd class="text-p-base text-ink-gray-8">
						<RouterLink
							class="hover:underline"
							:to="{
								name: 'SalesInvoiceDetail',
								params: { name: credit.sales_invoice },
							}"
						>
							{{ credit.sales_invoice }}
						</RouterLink>
					</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Requested</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ shortDate(credit.transaction_date) }}
					</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Reason</dt>
					<dd class="text-p-base text-ink-gray-8">{{ credit.reason }}</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">To credit</dt>
					<dd class="text-p-base font-medium text-ink-gray-8">
						{{ money(credit.total_amount, credit.currency) }}
					</dd>
				</div>
			</dl>

			<div v-if="credit.description" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Your note</p>
				<p class="mt-1 whitespace-pre-line text-p-base text-ink-gray-8">
					{{ credit.description }}
				</p>
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
						v-for="item in credit.items"
						:key="item.sales_invoice_item"
						class="grid gap-1 px-4 py-3 sm:grid-cols-12 sm:items-center sm:gap-3"
					>
						<p class="text-base font-medium text-ink-gray-8 sm:col-span-6">
							{{ item.item_name }}
						</p>
						<p class="text-p-sm text-ink-gray-7 sm:col-span-2">
							{{ item.qty }} {{ item.uom }}
						</p>
						<p class="text-p-sm text-ink-gray-7 sm:col-span-2">
							{{ money(item.rate, credit.currency) }}
						</p>
						<p
							class="text-p-sm font-medium text-ink-gray-8 sm:col-span-2 sm:text-right"
						>
							{{ money(item.amount, credit.currency) }}
						</p>
					</div>
				</div>

				<div
					class="flex items-center justify-between border-t bg-surface-gray-1 px-4 py-2 text-base font-medium text-ink-gray-8"
				>
					<span>Total before tax</span>
					<span>{{ money(credit.total_amount, credit.currency) }}</span>
				</div>
			</div>

			<ReturnNotes
				v-if="credit.credit_note"
				title="Credit note"
				:notes="[credit.credit_note]"
				:currency="credit.currency"
				detail-route="SalesInvoiceDetail"
				:status-theme="SALES_INVOICE_STATUS_THEME"
			/>
		</div>

		<Dialog
			v-model:open="confirmingWithdraw"
			title="Withdraw this request?"
			icon="lucide-undo-2"
			theme="amber"
			message="Our team stops reviewing it. You can raise a new request from the invoice later."
			:actions="[
				{
					label: 'Withdraw request',
					variant: 'solid',
					theme: 'red',
					loading: withdrawing,
					onClick: withdraw,
				},
			]"
		/>
	</PageContainer>
</template>
