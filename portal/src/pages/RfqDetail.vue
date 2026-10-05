<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Alert, Badge, Button, Dialog, ErrorMessage, FormControl, Spinner } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import RichText from "@/components/RichText.vue";
import PrintButton from "@/components/PrintButton.vue";
import {
	RFQ_STATUS_THEME,
	createRfqResource,
	declineQuote,
	saveQuote,
	sendQuote,
} from "@/data/rfq";
import type { QuoteLine, QuotePayload, Rfq } from "@/data/rfq";
import { isOk } from "@/types/api";
import { usePortalStore } from "@/stores/portal";
import { useIsMobile } from "@/composables/useViewport";
import { ACCENTS, LOOKS } from "@/data/accents";

const props = defineProps<{ name: string }>();

const isMobile = useIsMobile();

const portal = usePortalStore();
const router = useRouter();

const request = createRfqResource();

const prices = reactive<Record<string, { rate: number | null; lead_time_days: number | null }>>(
	{}
);
const reference = ref<string | null>(null);
const validTill = ref<string | null>(null);

const submitting = ref(false);
const saving = ref(false);
const savedMessage = ref<string | null>(null);
const errorMessage = ref<string | null>(null);
const declining = ref(false);
const declineReason = ref("");
const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);

const rfq = computed<Rfq | null>(() => request.data ?? null);

const isSealedBid = computed(() => rfq.value?.bidding_method === "Sealed Bid");

const total = computed(() =>
	(rfq.value?.items ?? []).reduce((sum, item) => {
		const rate = prices[item.name]?.rate;
		return sum + (rate ? rate * item.qty : 0);
	}, 0)
);

function fill(doc: Rfq) {
	for (const item of doc.items) {
		prices[item.name] = {
			rate: item.rate ?? null,
			lead_time_days: item.lead_time_days ?? null,
		};
	}
	reference.value = doc.quote?.quotation_number ?? null;
	validTill.value = doc.quote?.valid_till ?? null;
}

async function load() {
	if (!supplier.value) return;
	const doc = await request.fetch({ name: props.name, supplier: supplier.value });
	if (doc) fill(doc as Rfq);
}

watch([supplier, () => props.name], load, { immediate: true });

function lines(): QuoteLine[] {
	return (rfq.value?.items ?? []).map((item) => ({
		rfq_item: item.name,
		rate: prices[item.name]?.rate ?? null,
		lead_time_days: prices[item.name]?.lead_time_days ?? null,
	}));
}

function payload(): QuotePayload | null {
	if (!rfq.value || !supplier.value) return null;

	return {
		name: rfq.value.name,
		supplier: supplier.value,
		items: lines(),
		quotation_number: reference.value,
		valid_till: validTill.value,
	};
}

function show(updated: Rfq) {
	request.setData(updated);
	fill(updated);
}

async function saveDraft() {
	const quote = payload();
	if (!quote) return;

	errorMessage.value = null;
	savedMessage.value = null;
	saving.value = true;

	try {
		const response = await saveQuote(quote);
		if (!isOk(response)) {
			errorMessage.value = response.message || "We could not save your draft.";
			return;
		}
		show(response.data);
		savedMessage.value = response.message;
	} catch (error: any) {
		errorMessage.value =
			error?.messages?.[0] || error?.message || "We could not save your draft.";
	} finally {
		saving.value = false;
	}
}

async function send() {
	const quote = payload();
	if (!quote) return;

	errorMessage.value = null;
	savedMessage.value = null;
	submitting.value = true;

	try {
		show((await sendQuote(quote)) as Rfq);
	} catch (error: any) {
		errorMessage.value =
			error?.messages?.[0] || error?.message || "We could not send your quotation.";
	} finally {
		submitting.value = false;
	}
}

async function decline() {
	if (!rfq.value || !supplier.value) return;

	errorMessage.value = null;
	try {
		const updated = (await declineQuote(
			rfq.value.name,
			supplier.value,
			declineReason.value
		)) as Rfq;
		request.setData(updated);
		declining.value = false;
		declineReason.value = "";
	} catch (error: any) {
		errorMessage.value = error?.messages?.[0] || error?.message || "We could not record that.";
	}
}

function formatDate(value: string | null) {
	if (!value) return "—";
	return new Date(value).toLocaleDateString(undefined, {
		day: "numeric",
		month: "short",
		year: "numeric",
	});
}

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

function money(value: number) {
	return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
</script>

<template>
	<PageContainer
		:look="LOOKS.rfq"
		:title="rfq?.name || name"
		:copy="rfq?.name"
		:breadcrumbs="[
			{ label: 'Request for Quotation', route: { name: 'RfqList' } },
			{ label: rfq?.name || name },
		]"
	>
		<template #actions>
			<Badge
				v-if="rfq"
				:theme="RFQ_STATUS_THEME[rfq.status]"
				variant="subtle"
				:label="rfq.status"
			/>
			<PrintButton
				v-if="rfq"
				doctype="Request for Quotation"
				:name="rfq.name"
				:label="'request for quotation'"
			/>
		</template>

		<EmptyState
			v-if="!supplier"
			icon="lucide-truck"
			title="Switch to a supplier account"
			description="This request belongs to one of your supplier accounts. Pick it at the top of the sidebar."
		/>

		<div v-else-if="request.loading && !rfq" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="request.error"
			icon="lucide-file-x"
			title="We cannot show this request"
			description="It may have been sent to another of your accounts, or withdrawn."
		>
			<Button
				variant="subtle"
				label="Back to requests"
				@click="router.push({ name: 'RfqList' })"
			/>
		</EmptyState>

		<div v-else-if="rfq" class="space-y-6">
			<dl
				:class="ACCENTS[LOOKS.rfq.accent].panel"
				class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-2 lg:grid-cols-4"
			>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Quoting as</dt>
					<dd class="text-p-base text-ink-gray-8">{{ portal.activeParty?.title }}</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Sent</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ formatDate(rfq.transaction_date) }}
					</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Needed by</dt>
					<dd class="text-p-base text-ink-gray-8">{{ formatDate(rfq.required_by) }}</dd>
				</div>
				<div>
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Bids close</dt>
					<dd class="text-p-base text-ink-gray-8">
						{{ formatDateTime(rfq.closes_at) }}
					</dd>
				</div>
			</dl>

			<Alert
				v-if="isSealedBid && rfq.can_quote"
				theme="blue"
				icon="lucide-lock"
				title="This is a sealed bid"
				description="Once you send your quotation it cannot be changed."
			/>

			<div v-if="rfq.attachments.length" class="flex flex-wrap gap-2">
				<a
					v-for="file in rfq.attachments"
					:key="file.file_url"
					:href="file.file_url"
					target="_blank"
					rel="noopener"
					class="inline-flex items-center gap-1.5 rounded-4 border px-2 py-1 text-p-sm text-ink-gray-7 hover:bg-surface-gray-2"
				>
					<i class="lucide-paperclip size-3.5" />
					{{ file.file_name }}
				</a>
			</div>

			<div class="overflow-hidden rounded-6 border">
				<div
					class="hidden bg-surface-gray-1 px-4 py-2 text-xs uppercase tracking-wide text-ink-gray-5 sm:grid sm:grid-cols-12 sm:gap-3"
				>
					<span class="sm:col-span-5">Item</span>
					<span class="sm:col-span-2">Quantity</span>
					<span class="sm:col-span-2">Your price</span>
					<span class="sm:col-span-2">Lead time</span>
					<span class="sm:col-span-1 text-right">Amount</span>
				</div>

				<div class="divide-y">
					<div
						v-for="item in rfq.items"
						:key="item.name"
						class="grid gap-3 px-4 py-3 sm:grid-cols-12 sm:items-center"
					>
						<div class="sm:col-span-5">
							<p class="text-base font-medium text-ink-gray-8">
								{{ item.item_name || item.item_code }}
							</p>
							<p
								v-if="item.description"
								class="mt-0.5 line-clamp-2 text-p-sm text-ink-gray-5"
							>
								{{ item.description }}
							</p>
							<p v-if="item.supplier_part_no" class="mt-0.5 text-xs text-ink-gray-5">
								Your part no. {{ item.supplier_part_no }}
							</p>
						</div>

						<p class="text-p-sm text-ink-gray-7 sm:col-span-2">
							{{ item.qty }} {{ item.uom }}
						</p>

						<FormControl
							v-if="rfq.can_quote"
							class="sm:col-span-2"
							type="number"
							size="sm"
							placeholder="0.00"
							:label="isMobile ? 'Your price' : undefined"
							:model-value="prices[item.name]?.rate ?? undefined"
							@update:model-value="
								prices[item.name] = {
									...prices[item.name],
									rate: $event === '' ? null : Number($event),
								}
							"
						/>
						<p v-else class="text-p-sm text-ink-gray-7 sm:col-span-2">
							{{ item.rate ? money(item.rate) : "—" }}
						</p>

						<FormControl
							v-if="rfq.can_quote"
							class="sm:col-span-2"
							type="number"
							size="sm"
							placeholder="Days"
							:label="isMobile ? 'Lead time in days' : undefined"
							:model-value="prices[item.name]?.lead_time_days ?? undefined"
							@update:model-value="
								prices[item.name] = {
									...prices[item.name],
									lead_time_days: $event === '' ? null : Number($event),
								}
							"
						/>
						<p v-else class="text-p-sm text-ink-gray-7 sm:col-span-2">
							{{ item.lead_time_days ? `${item.lead_time_days} days` : "—" }}
						</p>

						<p
							class="text-p-sm font-medium text-ink-gray-8 sm:col-span-1 sm:text-right"
						>
							{{ money((prices[item.name]?.rate ?? 0) * item.qty) }}
						</p>
					</div>
				</div>

				<div
					class="flex items-center justify-between border-t bg-surface-gray-1 px-4 py-2 text-base font-medium text-ink-gray-8"
				>
					<span>Total</span>
					<span>{{ money(total) }}</span>
				</div>
			</div>

			<div v-if="rfq.can_quote" class="grid gap-4 sm:grid-cols-2">
				<FormControl
					v-model="reference"
					type="text"
					label="Your quotation number"
					placeholder="Optional — your own reference"
				/>
				<FormControl
					v-model="validTill"
					type="date"
					label="Prices valid until"
					description="We need this before you can submit."
				/>
			</div>

			<div v-if="rfq.terms" class="rounded-6 border p-4">
				<p class="text-xs uppercase tracking-wide text-ink-gray-5">Terms</p>
				<RichText class="mt-1" :html="rfq.terms" />
			</div>

			<div
				v-if="rfq.status === 'Draft'"
				class="rounded-6 border border-outline-amber-2 bg-surface-amber-1 p-4"
			>
				<p class="text-base font-medium text-ink-gray-8">This quotation is a draft</p>
				<p class="mt-1 text-p-sm text-ink-gray-6">
					{{ savedMessage || "Saved as Draft. You can revise later and then submit it" }}
				</p>
			</div>

			<ErrorMessage v-if="errorMessage" :message="errorMessage" />

			<div
				v-if="rfq.can_quote"
				class="flex flex-wrap items-center justify-between gap-3 border-t pt-4"
			>
				<Button
					variant="solid"
					theme="red"
					label="Not quoting"
					@click="declining = true"
				/>

				<div class="flex flex-wrap items-center gap-2">
					<Button
						variant="subtle"
						label="Save draft"
						:loading="saving"
						:disabled="submitting"
						@click="saveDraft"
					/>
					<Button
						variant="solid"
						theme="green"
						label="Send quotation"
						:loading="submitting"
						:disabled="saving"
						@click="send"
					/>
				</div>
			</div>

			<div
				v-else-if="rfq.status === 'Submitted'"
				class="rounded-6 border border-outline-green-2 bg-surface-green-1 p-4"
			>
				<p class="text-base font-medium text-ink-gray-8">
					{{
						rfq.sealed
							? "Your quotation is sealed"
							: "Your quotation is with the buyer"
					}}
				</p>
				<p class="mt-1 text-p-sm text-ink-gray-6">
					Sent as {{ rfq.quote?.name
					}}<template v-if="rfq.quote?.valid_till"
						>, valid until {{ formatDate(rfq.quote.valid_till) }}</template
					>.
					<template v-if="rfq.sealed">
						The committee opens all quotations together after
						{{ formatDateTime(rfq.closes_at) }}.
					</template>
				</p>
			</div>
		</div>

		<Dialog
			v-model:open="declining"
			title="Not quoting for this request"
			message="Let the buyer know why, so they can plan. You cannot quote after this, and any draft you saved is thrown away."
			icon="lucide-circle-x"
			theme="red"
			:actions="[
				{
					label: 'Confirm',
					variant: 'solid',
					theme: 'red',
					disabled: !declineReason.trim(),
					onClick: decline,
				},
			]"
		>
			<FormControl
				v-model="declineReason"
				type="textarea"
				placeholder="We do not stock this item at the moment."
			/>
		</Dialog>
	</PageContainer>
</template>
