<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	Badge,
	Button,
	ErrorMessage,
	FormControl,
	Spinner,
	TextInput,
	debounce,
	toast,
} from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import QtyStepper from "@/components/QtyStepper.vue";
import { money, shortDate } from "@/data/purchase";
import {
	fetchCreditForm,
	fetchCreditableInvoices,
	resubmitCreditRequest,
	submitCreditRequest,
} from "@/data/creditRequests";
import type { CreditForm, CreditableInvoice } from "@/data/creditRequests";
import { errorText } from "@/data/orders";
import { isOk } from "@/types/api";
import { usePortalStore } from "@/stores/portal";
import { ACCENTS, LOOKS } from "@/data/accents";

const props = defineProps<{ name?: string }>();

const portal = usePortalStore();
const route = useRoute();
const router = useRouter();

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const chosenInvoice = computed(() =>
	props.name ? null : typeof route.query.invoice === "string" ? route.query.invoice : null
);
const picking = computed(() => !props.name && !chosenInvoice.value);

const search = ref("");
const invoices = ref<CreditableInvoice[]>([]);
const loadingInvoices = ref(false);
const invoicesError = ref<string | null>(null);

async function loadInvoices() {
	if (!customer.value || !picking.value) return;

	loadingInvoices.value = true;
	invoicesError.value = null;
	try {
		const response = await fetchCreditableInvoices(customer.value, search.value);
		if (!isOk(response)) {
			invoicesError.value = response.message || "We could not load your invoices.";
			return;
		}
		invoices.value = response.data;
	} catch (error) {
		invoicesError.value = errorText(error, "We could not load your invoices.");
	} finally {
		loadingInvoices.value = false;
	}
}

const searchInvoices = debounce(loadInvoices, 300);
watch(search, () => searchInvoices());
onBeforeUnmount(() => searchInvoices.cancel());

function pickInvoice(invoice: CreditableInvoice) {
	if (invoice.open_request) {
		router.push({ name: "CreditRequestDetail", params: { name: invoice.open_request } });
		return;
	}
	router.replace({ query: { invoice: invoice.name } });
}

const form = ref<CreditForm | null>(null);
const loadingForm = ref(false);
const formError = ref<string | null>(null);
const openRequest = ref<string | null>(null);

const quantities = ref<Record<string, number>>({});
const reason = ref("");
const details = ref("");

async function loadForm() {
	form.value = null;
	formError.value = null;
	openRequest.value = null;
	if (!customer.value) return;

	if (picking.value) {
		loadInvoices();
		return;
	}

	loadingForm.value = true;
	try {
		const response = await fetchCreditForm({
			customer: customer.value,
			sales_invoice: chosenInvoice.value,
			name: props.name || null,
		});
		if (!isOk(response)) {
			formError.value = response.message || "We cannot start a request for this invoice.";
			openRequest.value =
				(response.data as { open_request?: string } | null)?.open_request ?? null;
			return;
		}

		form.value = response.data;
		quantities.value = Object.fromEntries(
			response.data.lines.map((line) => [line.sales_invoice_item, line.qty])
		);
		reason.value = response.data.request?.reason || "";
		details.value = response.data.request?.description || "";
	} catch (error) {
		formError.value = errorText(error, "We cannot start a request for this invoice.");
	} finally {
		loadingForm.value = false;
	}
}

watch([customer, () => props.name, chosenInvoice], loadForm, { immediate: true });

const currency = computed(() => form.value?.invoice.currency ?? null);

const chosenLines = computed(() =>
	(form.value?.lines ?? []).filter(
		(line) => (quantities.value[line.sales_invoice_item] || 0) > 0
	)
);

const total = computed(() =>
	chosenLines.value.reduce(
		(sum, line) => sum + (quantities.value[line.sales_invoice_item] || 0) * line.rate,
		0
	)
);

const detailsRequired = computed(() => reason.value === "Other");

const missing = computed(() => {
	if (!chosenLines.value.length) return "Set a quantity on at least one item.";
	if (!reason.value) return "Choose a reason.";
	if (detailsRequired.value && !details.value.trim()) return "Tell us what went wrong.";
	return null;
});

const sending = ref(false);
const sendError = ref<string | null>(null);

function creditAll() {
	for (const line of form.value?.lines ?? []) {
		quantities.value[line.sales_invoice_item] = line.available_qty;
	}
}

async function send() {
	if (!customer.value || !form.value || missing.value) return;

	sending.value = true;
	sendError.value = null;
	const payload = {
		customer: customer.value,
		items: chosenLines.value.map((line) => ({
			sales_invoice_item: line.sales_invoice_item,
			qty: quantities.value[line.sales_invoice_item],
		})),
		reason: reason.value,
		description: details.value.trim() || null,
	};

	try {
		const response = props.name
			? await resubmitCreditRequest({ ...payload, name: props.name })
			: await submitCreditRequest({ ...payload, sales_invoice: form.value.invoice.name });
		if (!isOk(response)) {
			sendError.value = response.message || "We could not send your request.";
			return;
		}
		toast.success(response.message || "Request sent.");
		router.push({ name: "CreditRequestDetail", params: { name: response.data.name } });
	} catch (error) {
		sendError.value = errorText(error, "We could not send your request.");
	} finally {
		sending.value = false;
	}
}

const title = computed(() => (props.name ? `Change ${props.name}` : "Request a credit note"));
</script>

<template>
	<PageContainer
		:look="LOOKS.creditRequest"
		:title="title"
		:wide="!picking"
		:breadcrumbs="[
			{ label: 'Credit Note Requests', route: { name: 'CreditRequestList' } },
			...(name
				? [
						{ label: name, route: { name: 'CreditRequestDetail', params: { name } } },
						{ label: 'Change' },
				  ]
				: [{ label: 'New request' }]),
		]"
	>
		<EmptyState
			v-if="!customer"
			icon="lucide-store"
			title="Switch to a customer account"
			description="Credit note requests belong to your customer accounts. Pick one at the top of the sidebar."
		/>

		<section v-else-if="picking" class="space-y-4" aria-label="Choose an invoice">
			<div>
				<h2 class="text-lg font-semibold text-ink-gray-9">
					Which invoice should we credit?
				</h2>
				<p class="mt-1 text-p-sm text-ink-gray-5">
					Only invoices with something left to credit are listed.
				</p>
			</div>

			<TextInput
				v-model="search"
				type="text"
				placeholder="Search by invoice or PO number"
				aria-label="Search invoices"
			>
				<template #prefix>
					<i class="lucide-search size-4 text-ink-gray-5" />
				</template>
			</TextInput>

			<ErrorMessage v-if="invoicesError" :message="invoicesError" />

			<div v-if="loadingInvoices && !invoices.length" class="flex justify-center py-16">
				<Spinner class="size-5" />
			</div>

			<EmptyState
				v-else-if="!invoices.length"
				icon="lucide-receipt-text"
				:title="search ? 'No invoice matches that number' : 'No invoices to credit'"
				:description="
					search
						? 'Check the number, or clear the search.'
						: 'Invoices that are already fully credited do not appear here.'
				"
			/>

			<ul v-else class="divide-y rounded-6 border">
				<li v-for="invoice in invoices" :key="invoice.name">
					<button
						type="button"
						class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-gray-1"
						@click="pickInvoice(invoice)"
					>
						<span class="min-w-0">
							<span class="block truncate text-base font-medium text-ink-gray-8">
								{{ invoice.name }}
							</span>
							<span class="block truncate text-p-sm text-ink-gray-5">
								{{ shortDate(invoice.posting_date) }}
								<template v-if="invoice.po_no"> · PO {{ invoice.po_no }}</template>
							</span>
						</span>
						<span class="flex shrink-0 items-center gap-2">
							<Badge
								v-if="invoice.open_request"
								theme="violet"
								variant="subtle"
								:label="`${invoice.open_request} open`"
							/>
							<span v-else class="text-p-base text-ink-gray-8">
								{{ money(invoice.grand_total, invoice.currency) }}
							</span>
							<i
								class="lucide-chevron-right size-4 text-ink-gray-4"
								aria-hidden="true"
							/>
						</span>
					</button>
				</li>
			</ul>
		</section>

		<div v-else-if="loadingForm" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="formError"
			icon="lucide-receipt-text"
			title="We cannot start this request"
			:description="formError"
		>
			<Button
				v-if="openRequest"
				variant="solid"
				:label="`Open ${openRequest}`"
				:route="{ name: 'CreditRequestDetail', params: { name: openRequest } }"
			/>
			<Button
				v-if="!name"
				variant="subtle"
				label="Choose another invoice"
				@click="router.replace({ query: {} })"
			/>
		</EmptyState>

		<div
			v-else-if="form"
			class="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start"
		>
			<div class="min-w-0 space-y-6">
				<div
					v-if="form.request?.review_remarks"
					class="rounded-6 border border-outline-amber-2 bg-surface-amber-1 p-4"
				>
					<p class="text-base font-medium text-ink-gray-8">What we need you to change</p>
					<p class="mt-1 whitespace-pre-line text-p-sm text-ink-gray-7">
						{{ form.request.review_remarks }}
					</p>
				</div>

				<div
					:class="ACCENTS[LOOKS.salesInvoice.accent].panel"
					class="flex flex-wrap items-center justify-between gap-3 rounded-6 border p-4"
				>
					<dl class="flex flex-wrap gap-x-8 gap-y-2">
						<div>
							<dt class="text-xs uppercase tracking-wide text-ink-gray-5">
								Invoice
							</dt>
							<dd class="text-p-base font-medium text-ink-gray-8">
								<RouterLink
									class="hover:underline"
									:to="{
										name: 'SalesInvoiceDetail',
										params: { name: form.invoice.name },
									}"
								>
									{{ form.invoice.name }}
								</RouterLink>
							</dd>
						</div>
						<div>
							<dt class="text-xs uppercase tracking-wide text-ink-gray-5">Dated</dt>
							<dd class="text-p-base text-ink-gray-8">
								{{ shortDate(form.invoice.posting_date) }}
							</dd>
						</div>
						<div v-if="form.invoice.po_no">
							<dt class="text-xs uppercase tracking-wide text-ink-gray-5">
								Your PO
							</dt>
							<dd class="text-p-base text-ink-gray-8">{{ form.invoice.po_no }}</dd>
						</div>
						<div>
							<dt class="text-xs uppercase tracking-wide text-ink-gray-5">
								Invoice total
							</dt>
							<dd class="text-p-base text-ink-gray-8">
								{{ money(form.invoice.grand_total, currency) }}
							</dd>
						</div>
					</dl>
					<Button
						v-if="!name"
						variant="outline"
						icon-left="lucide-arrow-left-right"
						label="Change invoice"
						@click="router.replace({ query: {} })"
					/>
				</div>

				<section aria-labelledby="credit-reason" class="space-y-4">
					<h2 id="credit-reason" class="text-lg font-semibold text-ink-gray-9">
						Why should we credit it?
					</h2>
					<FormControl
						v-model="reason"
						class="sm:w-80"
						type="select"
						label="Reason"
						placeholder="Choose a reason"
						:options="form.reasons.map((option) => ({ label: option, value: option }))"
						required
					/>
					<FormControl
						v-model="details"
						type="textarea"
						:label="
							detailsRequired
								? 'What went wrong'
								: 'Anything we should know (optional)'
						"
						placeholder="e.g. 2 cartons arrived crushed"
						:rows="3"
						maxlength="1000"
						:required="detailsRequired"
					/>
				</section>

				<section aria-labelledby="credit-items">
					<div class="mb-2 flex flex-wrap items-end justify-between gap-2">
						<div>
							<h2 id="credit-items" class="text-lg font-semibold text-ink-gray-9">
								What should we credit?
							</h2>
							<p class="text-p-sm text-ink-gray-5">
								Set how many of each item to credit. Leave the rest at 0.
							</p>
						</div>
						<Button
							variant="outline"
							icon-left="lucide-list-checks"
							label="Credit all remaining"
							@click="creditAll"
						/>
					</div>

					<ul class="divide-y rounded-6 border">
						<li
							v-for="line in form.lines"
							:key="line.sales_invoice_item"
							class="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
							:class="line.available_qty <= 0 ? 'bg-surface-gray-1' : ''"
						>
							<div class="min-w-0">
								<p class="text-base font-medium text-ink-gray-8">
									{{ line.item_name }}
								</p>
								<p
									v-if="line.description && line.description !== line.item_name"
									class="mt-0.5 line-clamp-2 text-p-sm text-ink-gray-5"
								>
									{{ line.description }}
								</p>
								<p class="mt-1 text-p-sm text-ink-gray-6">
									{{ line.invoiced_qty }} {{ line.uom }} invoiced at
									{{ money(line.rate, currency) }}
									<template v-if="line.credited_qty">
										· {{ line.credited_qty }} already credited
									</template>
								</p>
							</div>

							<Badge
								v-if="line.available_qty <= 0"
								theme="gray"
								variant="subtle"
								label="Fully credited"
							/>
							<div
								v-else
								class="flex shrink-0 items-center justify-between gap-4 sm:justify-end"
							>
								<div class="w-36">
									<QtyStepper
										v-model="quantities[line.sales_invoice_item]"
										:label="line.item_name"
										:max="line.available_qty"
										:removable="false"
										size="sm"
									/>
									<p class="mt-1 text-center text-xs text-ink-gray-5">
										of {{ line.available_qty }} {{ line.uom }}
									</p>
								</div>
								<p class="w-28 text-right text-p-base font-medium text-ink-gray-8">
									{{
										money(
											(quantities[line.sales_invoice_item] || 0) * line.rate,
											currency
										)
									}}
								</p>
							</div>
						</li>
					</ul>
				</section>
			</div>

			<aside
				class="sticky bottom-3 z-10 rounded-8 border bg-surface-base p-4 shadow-[0_8px_24px_rgba(0,0,0,0.12)] lg:top-6 lg:shadow-none"
			>
				<div class="flex items-baseline justify-between gap-2">
					<span class="text-p-sm text-ink-gray-6">
						{{ chosenLines.length }}
						{{ chosenLines.length === 1 ? "item" : "items" }} to credit
					</span>
					<span class="text-lg font-semibold text-ink-gray-9">
						{{ money(total, currency) }}
					</span>
				</div>
				<p class="mt-1 hidden text-p-xs text-ink-gray-5 lg:block">
					Before tax. Our accounts team reviews every request, and the credit note shows
					the final amount.
				</p>

				<ErrorMessage v-if="sendError" class="mt-3" :message="sendError" />

				<Button
					class="mt-3 w-full"
					variant="solid"
					size="md"
					:label="name ? 'Resubmit request' : 'Send request'"
					:loading="sending"
					:disabled="!!missing"
					@click="send"
				/>
				<p v-if="missing" class="mt-2 text-center text-p-xs text-ink-gray-5">
					{{ missing }}
				</p>
			</aside>
		</div>
	</PageContainer>
</template>
