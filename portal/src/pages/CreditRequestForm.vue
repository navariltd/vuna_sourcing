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
import ExplainerAccordion from "@/components/ExplainerAccordion.vue";
import EmptyState from "@/components/EmptyState.vue";
import { money, shortDate } from "@/data/purchase";
import {
	CREDIT_REQUEST_EXPLAINER,
	fetchCreditableInvoices,
	fetchCreditForm,
	percentOff,
	priceAfter,
	resubmitCreditRequest,
	submitCreditRequest,
} from "@/data/creditRequests";
import type { CreditableInvoice, CreditForm, CreditFormLine } from "@/data/creditRequests";
import { errorText } from "@/data/orders";
import { isOk } from "@/types/api";
import { usePortalStore } from "@/stores/portal";
import { ACCENTS, LOOKS } from "@/data/accents";
import { useIsWide } from "@/composables/useViewport";

const props = defineProps<{ name?: string }>();

const isWide = useIsWide();

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

const prices = ref<Record<string, number | null>>({});
const percents = ref<Record<string, number | null>>({});
const percentForAll = ref<number | null>(null);
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
		prices.value = Object.fromEntries(
			response.data.lines.map((line) => [line.sales_invoice_item, line.new_rate])
		);
		percents.value = Object.fromEntries(
			response.data.lines.map((line) => [
				line.sales_invoice_item,
				percentOff(line.rate, line.new_rate),
			])
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

const adjustable = (line: CreditFormLine) => line.available_qty > 0 && line.rate > 0;

const adjustableLines = computed(() => (form.value?.lines ?? []).filter(adjustable));

function asNumber(value: string | number) {
	return value === "" || value === null ? null : Number(value);
}

function setPrice(line: CreditFormLine, value: string | number) {
	const price = asNumber(value);
	prices.value[line.sales_invoice_item] = price;
	percents.value[line.sales_invoice_item] = price === null ? null : percentOff(line.rate, price);
}

function setPercent(line: CreditFormLine, value: string | number) {
	const percent = asNumber(value);
	percents.value[line.sales_invoice_item] = percent;
	if (percent !== null && percent >= 0 && percent <= 100) {
		prices.value[line.sales_invoice_item] = priceAfter(line.rate, percent);
	}
}

function applyToAll() {
	const percent = percentForAll.value;
	if (percent === null || percent <= 0 || percent > 100) return;
	for (const line of adjustableLines.value) setPercent(line, percent);
}

const pricesChanged = computed(() =>
	adjustableLines.value.some((line) => prices.value[line.sales_invoice_item] !== line.rate)
);

function resetPrices() {
	for (const line of adjustableLines.value) setPrice(line, line.rate);
	percentForAll.value = null;
}

function newTotal(line: CreditFormLine) {
	return (prices.value[line.sales_invoice_item] ?? 0) * line.available_qty;
}

function lineProblem(line: CreditFormLine): string | null {
	const price = prices.value[line.sales_invoice_item];
	const percent = percents.value[line.sales_invoice_item];
	if (price === null) return "Enter a new price, or reset the line.";
	if (price < 0) return "The new price cannot be below zero.";
	if (price > line.rate) return `Must be at most ${money(line.rate, currency.value)}.`;
	if (percent !== null && (percent < 0 || percent > 100))
		return "Use a percentage from 0 to 100.";
	return null;
}

function reduction(line: CreditFormLine) {
	const price = prices.value[line.sales_invoice_item];
	if (price === null || lineProblem(line)) return 0;
	return Math.max(line.rate - price, 0) * line.available_qty;
}

const loweredLines = computed(() =>
	adjustableLines.value.filter((line) => !lineProblem(line) && reduction(line) > 0)
);

const total = computed(() => loweredLines.value.reduce((sum, line) => sum + reduction(line), 0));

const detailsRequired = computed(() => reason.value === "Other");

const missing = computed(() => {
	if (adjustableLines.value.some(lineProblem)) return "Fix the prices marked in red.";
	if (!loweredLines.value.length) return "Lower the price of at least one item.";
	if (!reason.value) return "Choose a reason.";
	if (detailsRequired.value && !details.value.trim())
		return "Tell us why the price should be lower.";
	return null;
});

const sending = ref(false);
const sendError = ref<string | null>(null);

async function send() {
	if (!customer.value || !form.value || missing.value) return;

	sending.value = true;
	sendError.value = null;
	const payload = {
		customer: customer.value,
		items: loweredLines.value.map((line) => ({
			sales_invoice_item: line.sales_invoice_item,
			new_rate: prices.value[line.sales_invoice_item] as number,
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
			<ExplainerAccordion
				:question="CREDIT_REQUEST_EXPLAINER.title"
				:answer="CREDIT_REQUEST_EXPLAINER.description"
			/>

			<div>
				<h2 class="text-lg font-semibold text-ink-gray-9">
					Which invoice should we credit?
				</h2>
				<p class="mt-1 text-p-sm text-ink-gray-5">
					Only invoices with items left to credit are listed.
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

		<div v-else-if="form" class="space-y-6">
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

				<ExplainerAccordion
					v-else
					:question="CREDIT_REQUEST_EXPLAINER.title"
					:answer="CREDIT_REQUEST_EXPLAINER.description"
				/>

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
						Why should the price be lower?
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
							detailsRequired ? 'Tell us why' : 'Anything we should know (optional)'
						"
						placeholder="e.g. We agreed 90 per carton on the phone with your sales team"
						:rows="3"
						maxlength="1000"
						:required="detailsRequired"
					/>
				</section>

				<section aria-labelledby="credit-items">
					<div class="mb-2 flex flex-wrap items-end justify-between gap-3">
						<div>
							<h2 id="credit-items" class="text-lg font-semibold text-ink-gray-9">
								New prices
							</h2>
							<p class="text-p-sm text-ink-gray-5">
								Type a new price or a percentage off for each item, or apply one
								percentage to all. Items marked Not changed are left out.
							</p>
						</div>
						<form class="flex items-end gap-2" @submit.prevent="applyToAll">
							<FormControl
								class="w-28"
								type="number"
								size="sm"
								label="% off all"
								placeholder="e.g. 10"
								min="0"
								max="100"
								step="any"
								:model-value="percentForAll ?? undefined"
								@update:model-value="percentForAll = asNumber($event)"
							/>
							<Button
								type="submit"
								variant="solid"
								icon-left="lucide-percent"
								label="Apply"
								:disabled="
									percentForAll === null ||
									percentForAll <= 0 ||
									percentForAll > 100
								"
							/>
							<Button
								variant="outline"
								icon-left="lucide-rotate-ccw"
								label="Reset prices"
								:disabled="!pricesChanged"
								@click="resetPrices"
							/>
						</form>
					</div>

					<div class="overflow-hidden rounded-6 border">
						<div
							class="hidden bg-surface-gray-1 px-4 py-2 text-xs uppercase tracking-wide text-ink-gray-5 xl:grid xl:grid-cols-[minmax(12rem,1fr)_10rem_12rem_6.5rem_11rem] xl:gap-4"
						>
							<span>Item</span>
							<span class="text-right">Invoiced price</span>
							<span>New price</span>
							<span>% off</span>
							<span class="text-right">Reduction</span>
						</div>

						<ul class="divide-y">
							<li
								v-for="line in form.lines"
								:key="line.sales_invoice_item"
								class="grid grid-cols-2 gap-x-3 gap-y-2 px-4 py-3 xl:grid-cols-[minmax(12rem,1fr)_10rem_12rem_6.5rem_11rem] xl:items-start xl:gap-x-4"
								:class="adjustable(line) ? '' : 'bg-surface-gray-1'"
							>
								<div class="col-span-2 min-w-0 xl:col-span-1">
									<p class="text-base font-medium text-ink-gray-8">
										{{ line.item_name }}
									</p>
									<p class="mt-0.5 text-p-sm text-ink-gray-6">
										{{ line.available_qty }} {{ line.uom }}
										<template v-if="line.credited_qty">
											· {{ line.credited_qty }} already credited
										</template>
									</p>
								</div>

								<p
									class="col-span-2 whitespace-nowrap text-p-sm tabular-nums text-ink-gray-7 xl:col-span-1 xl:pt-1.5 xl:text-right"
								>
									<span class="text-ink-gray-5 xl:hidden">Invoiced at </span>
									{{ money(line.rate, currency) }}
								</p>

								<div
									v-if="!adjustable(line)"
									class="col-span-2 xl:col-span-3 xl:text-right"
								>
									<Badge
										theme="gray"
										variant="subtle"
										:label="
											line.available_qty > 0
												? 'No price to lower'
												: 'Fully credited'
										"
									/>
								</div>

								<template v-else>
									<div class="min-w-0">
										<FormControl
											type="number"
											size="sm"
											min="0"
											:max="line.rate"
											step="any"
											:label="isWide ? undefined : 'New price'"
											:aria-label="`New price for ${line.item_name}`"
											:model-value="
												prices[line.sales_invoice_item] ?? undefined
											"
											@update:model-value="setPrice(line, $event)"
										/>
										<p
											v-if="lineProblem(line)"
											class="mt-1 flex items-start gap-1 text-p-xs text-ink-red-6"
											role="alert"
										>
											<i
												class="lucide-circle-alert mt-0.5 size-3.5 shrink-0"
												aria-hidden="true"
											/>
											{{ lineProblem(line) }}
										</p>
										<p
											v-else
											class="mt-1 whitespace-nowrap text-p-xs tabular-nums text-ink-gray-6"
										>
											New total
											<span class="font-medium text-ink-gray-8">
												{{ money(newTotal(line), currency) }}
											</span>
										</p>
									</div>

									<FormControl
										type="number"
										size="sm"
										min="0"
										max="100"
										step="any"
										:label="isWide ? undefined : '% off'"
										:aria-label="`Percentage off ${line.item_name}`"
										:model-value="
											percents[line.sales_invoice_item] ?? undefined
										"
										@update:model-value="setPercent(line, $event)"
									/>

									<div
										class="col-span-2 flex items-end justify-end xl:col-span-1 xl:pt-1"
									>
										<span
											v-if="reduction(line) > 0"
											class="whitespace-nowrap text-base font-medium tabular-nums text-ink-green-7"
										>
											−{{ money(reduction(line), currency) }}
										</span>
										<span
											v-else-if="!lineProblem(line)"
											class="inline-flex items-center gap-1 rounded-full border border-outline-amber-2 bg-surface-amber-1 px-2 py-0.5 text-p-xs text-ink-amber-7"
										>
											<i
												class="lucide-circle-alert size-3.5"
												aria-hidden="true"
											/>
											Not changed
										</span>
										<span v-else class="text-p-sm text-ink-gray-4">—</span>
									</div>
								</template>
							</li>
						</ul>

						<div
							class="flex items-center justify-between border-t bg-surface-gray-1 px-4 py-2 text-base font-medium text-ink-gray-8"
						>
							<span>Total reduction before tax</span>
							<span class="whitespace-nowrap tabular-nums">{{
								money(total, currency)
							}}</span>
						</div>
					</div>
				</section>
			</div>

			<aside
				class="sticky bottom-3 z-10 rounded-8 border bg-surface-base p-4 shadow-[0_8px_24px_rgba(0,0,0,0.12)]"
			>
				<div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
					<div class="min-w-0">
						<div class="flex items-baseline justify-between gap-3 lg:justify-start">
							<span class="text-p-sm text-ink-gray-6">
								{{ loweredLines.length }}
								{{ loweredLines.length === 1 ? "item" : "items" }} lowered
							</span>
							<span
								class="whitespace-nowrap text-lg font-semibold tabular-nums text-ink-gray-9"
							>
								{{ money(total, currency) }}
							</span>
						</div>
						<p class="mt-1 hidden text-p-xs text-ink-gray-5 lg:block">
							Before tax. Our accounts team reviews every request, and the credit
							note shows the final amount.
						</p>
					</div>

					<div class="flex flex-col gap-2 lg:items-end">
						<Button
							class="w-full lg:w-48"
							variant="solid"
							size="md"
							:label="name ? 'Resubmit request' : 'Send request'"
							:loading="sending"
							:disabled="!!missing"
							@click="send"
						/>
						<p
							v-if="missing"
							class="flex items-center justify-center gap-1 text-p-sm text-ink-red-6"
							role="alert"
						>
							<i class="lucide-circle-alert size-4 shrink-0" aria-hidden="true" />
							{{ missing }}
						</p>
					</div>
				</div>

				<ErrorMessage v-if="sendError" class="mt-3" :message="sendError" />
			</aside>
		</div>
	</PageContainer>
</template>
