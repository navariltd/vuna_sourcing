<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import {
	Badge,
	Button,
	Checkbox,
	Dialog,
	ErrorMessage,
	FormControl,
	FormLabel,
	Select,
	Spinner,
	TextInput,
	toast,
} from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import ItemLink from "@/components/ItemLink.vue";
import { money } from "@/data/purchase";
import {
	deleteOrder,
	errorText,
	fetchOrderForm,
	priceOrder,
	saveOrder,
	submitOrder,
} from "@/data/orders";
import type {
	OrderForm,
	OrderLineView,
	OrderPayload,
	OrderView,
	OrderableItem,
	OrderableUom,
} from "@/data/orders";
import { isOk } from "@/types/api";
import { usePortalStore } from "@/stores/portal";
import { ACCENTS, LOOKS } from "@/data/accents";

const props = defineProps<{ name?: string }>();

interface OrderLine {
	id: number;
	item_code: string | null;
	item_name: string;
	uom: string;
	uoms: OrderableUom[];
	qty: number;
}

const GRID_COLUMNS = "minmax(220px, 3fr) 120px 110px minmax(180px, 1fr) minmax(200px, 1fr)";

const portal = usePortalStore();
const router = useRouter();

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const form = ref<OrderForm | null>(null);
const loading = ref(false);
const unavailable = ref<string | null>(null);

const orderName = ref<string | null>(null);
const company = ref<string | null>(null);
const address = ref<string | null>(null);
const deliveryDate = ref<string | null>(null);
const poNo = ref("");
const lines = ref<OrderLine[]>([]);
const selected = ref(new Set<number>());
const savedSnapshot = ref("");
const leaving = ref(false);
const loadedFor = ref<string | null>(null);

let nextLineId = 1;
let pricedKey = "";
let priceTimer: ReturnType<typeof setTimeout> | undefined;
let priceRequest = 0;

const priced = ref<OrderView | null>(null);
const pricing = ref(false);
const pricingError = ref<string | null>(null);

const busy = ref<"draft" | "send" | "delete" | null>(null);
const errorMessage = ref<string | null>(null);
const confirmingSend = ref(false);
const confirmingDelete = ref(false);

const companies = computed(() => form.value?.companies ?? []);
const addresses = computed(() => form.value?.addresses ?? []);
const currency = computed(() => priced.value?.currency ?? null);
const filledLines = computed(() =>
	lines.value.filter((line): line is OrderLine & { item_code: string } => !!line.item_code)
);

function emptyLine(): OrderLine {
	return { id: nextLineId++, item_code: null, item_name: "", uom: "", uoms: [], qty: 1 };
}

function linesFrom(items: OrderLineView[]): OrderLine[] {
	return items.map((item) => ({
		id: nextLineId++,
		item_code: item.item_code,
		item_name: item.item_name,
		uom: item.uom,
		uoms: item.uoms,
		qty: item.qty,
	}));
}

function orderedItems() {
	return filledLines.value.map(({ item_code, uom, qty }) => ({ item_code, uom, qty }));
}

function snapshot() {
	return JSON.stringify({
		company: company.value,
		address: address.value,
		deliveryDate: deliveryDate.value,
		poNo: poNo.value.trim(),
		lines: orderedItems(),
	});
}

const dirty = computed(() => snapshot() !== savedSnapshot.value);

function showLines(items: OrderLineView[]) {
	lines.value = items.length ? linesFrom(items) : [emptyLine()];
	selected.value = new Set();
}

function fill(data: OrderForm) {
	const order = data.order;
	orderName.value = order?.name ?? null;
	company.value = order?.company ?? (data.companies.length === 1 ? data.companies[0]! : null);
	address.value =
		order?.shipping_address ?? (data.addresses.length === 1 ? data.addresses[0]!.name : null);
	deliveryDate.value = order?.delivery_date ?? null;
	poNo.value = order?.po_no ?? "";
	showLines(order?.items ?? []);
	priced.value = order;
	pricedKey = priceKey();
	savedSnapshot.value = snapshot();
}

async function load() {
	if (!customer.value) return;
	if (
		props.name &&
		props.name === orderName.value &&
		form.value &&
		loadedFor.value === customer.value
	)
		return;

	loading.value = true;
	unavailable.value = null;
	errorMessage.value = null;

	try {
		const response = await fetchOrderForm(customer.value, props.name);
		if (!isOk(response)) {
			form.value = null;
			unavailable.value = response.message || "Ordering is not available for this account.";
			return;
		}
		form.value = response.data;
		loadedFor.value = customer.value;
		fill(response.data);
	} catch (error) {
		form.value = null;
		unavailable.value = errorText(error, "We cannot open this order.");
	} finally {
		loading.value = false;
	}
}

watch([customer, () => props.name], load, { immediate: true });

function priceKey() {
	return JSON.stringify({
		company: company.value,
		address: address.value,
		items: orderedItems(),
	});
}

function schedulePricing() {
	clearTimeout(priceTimer);
	const key = priceKey();
	if (key === pricedKey) return;

	if (!customer.value || !company.value || !filledLines.value.length) {
		priced.value = null;
		pricedKey = key;
		pricingError.value = null;
		return;
	}

	priceTimer = setTimeout(() => runPricing(key), 350);
}

async function runPricing(key: string) {
	const request = ++priceRequest;
	pricing.value = true;

	try {
		const response = await priceOrder({
			customer: customer.value!,
			company: company.value,
			items: orderedItems(),
			delivery_date: deliveryDate.value,
			shipping_address: address.value,
		});
		if (request !== priceRequest) return;

		pricedKey = key;
		if (isOk(response)) {
			priced.value = response.data;
			pricingError.value = null;
		} else {
			pricingError.value = response.message;
		}
	} catch (error) {
		if (request !== priceRequest) return;
		pricedKey = key;
		pricingError.value = errorText(error, "We could not price your order.");
	} finally {
		if (request === priceRequest) pricing.value = false;
	}
}

watch(priceKey, schedulePricing);
onBeforeUnmount(() => clearTimeout(priceTimer));

function pricedLine(line: OrderLine) {
	if (!line.item_code || priceKey() !== pricedKey) return null;
	return priced.value?.items.find(
		(item) => item.item_code === line.item_code && item.uom === line.uom
	);
}

function twinOf(line: OrderLine, item_code: string, uom: string) {
	return lines.value.find(
		(other) => other !== line && other.item_code === item_code && other.uom === uom
	);
}

function removeLines(ids: Set<number>) {
	lines.value = lines.value.filter((line) => !ids.has(line.id));
	selected.value = new Set([...selected.value].filter((id) => !ids.has(id)));
	if (!lines.value.length) lines.value = [emptyLine()];
}

function selectItem(line: OrderLine, item: OrderableItem) {
	const twin = twinOf(line, item.item_code, item.uom);
	if (twin) {
		twin.qty += line.qty;
		removeLines(new Set([line.id]));
		toast.info(`${item.item_name} is already on this order, so we added to that line.`);
		return;
	}

	Object.assign(line, {
		item_code: item.item_code,
		item_name: item.item_name,
		uom: item.uom,
		uoms: item.uoms,
	});
}

function changeUom(line: OrderLine, uom: string) {
	const twin = line.item_code ? twinOf(line, line.item_code, uom) : null;
	if (twin) {
		twin.qty += line.qty;
		removeLines(new Set([line.id]));
		return;
	}
	line.uom = uom;
}

function setQty(line: OrderLine, value: string | number) {
	const qty = Number(value);
	if (!Number.isFinite(qty) || qty <= 0) return;
	line.qty = qty;
}

function addRow() {
	lines.value.push(emptyLine());
}

const allSelected = computed(
	() => lines.value.length > 0 && lines.value.every((line) => selected.value.has(line.id))
);

function toggleAll(value: boolean) {
	selected.value = value ? new Set(lines.value.map((line) => line.id)) : new Set();
}

function toggleLine(line: OrderLine, value: boolean) {
	const next = new Set(selected.value);
	if (value) next.add(line.id);
	else next.delete(line.id);
	selected.value = next;
}

function deleteSelected() {
	removeLines(selected.value);
}

const checklist = computed(() => [
	{ label: "Choose the company you are ordering from", done: !!company.value },
	{
		label: "Choose a delivery address",
		done: addresses.value.length <= 1 || !!address.value,
	},
	{ label: "Choose a delivery date", done: !!deliveryDate.value },
	{ label: "Add at least one item", done: filledLines.value.length > 0 },
]);

const missing = computed(() => checklist.value.filter((step) => !step.done));

const ready = computed(() => !missing.value.length && !busy.value);

function payload(): OrderPayload {
	return {
		customer: customer.value!,
		company: company.value,
		name: orderName.value,
		items: orderedItems(),
		delivery_date: deliveryDate.value,
		shipping_address: address.value,
		po_no: poNo.value.trim() || null,
	};
}

function adopt(order: OrderView) {
	orderName.value = order.name;
	showLines(order.items);
	priced.value = order;
	pricedKey = priceKey();
	pricingError.value = null;
	savedSnapshot.value = snapshot();
}

async function saveDraft() {
	if (!ready.value) return;

	busy.value = "draft";
	errorMessage.value = null;

	try {
		const response = await saveOrder(payload());
		if (!isOk(response)) {
			errorMessage.value = response.message || "We could not save your draft.";
			return;
		}

		const isNew = !orderName.value;
		adopt(response.data);
		toast.success(response.message || "Draft saved.");
		if (isNew && response.data.name) {
			router.replace({ name: "SalesOrderEdit", params: { name: response.data.name } });
		}
	} catch (error) {
		errorMessage.value = errorText(error, "We could not save your draft.");
	} finally {
		busy.value = null;
	}
}

async function send() {
	if (!ready.value) return;

	busy.value = "send";
	errorMessage.value = null;

	try {
		const response = await submitOrder(payload());
		if (!isOk(response)) {
			errorMessage.value = response.message || "We could not send your order.";
			return;
		}

		adopt(response.data);
		confirmingSend.value = false;
		leaving.value = true;
		toast.success(response.message || "Order sent.");
		router.push({ name: "SalesOrderDetail", params: { name: response.data.name! } });
	} catch (error) {
		confirmingSend.value = false;
		errorMessage.value = errorText(error, "We could not send your order.");
	} finally {
		busy.value = null;
	}
}

async function removeDraft() {
	if (!orderName.value || !customer.value) return;

	busy.value = "delete";
	errorMessage.value = null;

	try {
		const response = await deleteOrder(customer.value, orderName.value);
		if (!isOk(response)) {
			errorMessage.value = response.message || "We could not delete this draft.";
			return;
		}

		confirmingDelete.value = false;
		leaving.value = true;
		toast.success(response.message || "Draft deleted.");
		router.push({ name: "SalesOrderList" });
	} catch (error) {
		confirmingDelete.value = false;
		errorMessage.value = errorText(error, "We could not delete this draft.");
	} finally {
		busy.value = null;
	}
}

onBeforeRouteLeave((to) => {
	if (leaving.value || !dirty.value || !form.value) return true;
	if (to.name === "SalesOrderEdit" && to.params.name === orderName.value) return true;
	return window.confirm("You have changes that are not saved. Leave this order anyway?");
});

const title = computed(() => (orderName.value ? `Draft ${orderName.value}` : "New order"));
</script>

<template>
	<PageContainer
		:look="LOOKS.salesOrder"
		fluid
		sticky-header
		:title="title"
		:breadcrumbs="[
			{ label: 'Sales Orders', route: { name: 'SalesOrderList' } },
			{ label: orderName ? orderName : 'New order' },
		]"
	>
		<template #actions>
			<template v-if="form && !unavailable">
				<Badge v-if="orderName" theme="gray" variant="subtle" label="Draft" />
				<Button
					v-if="orderName"
					variant="subtle"
					theme="red"
					icon-left="lucide-trash-2"
					label="Delete draft"
					:disabled="!!busy"
					@click="confirmingDelete = true"
				/>
				<Button
					variant="subtle"
					:label="dirty || !orderName ? 'Save draft' : 'Draft saved'"
					:disabled="!ready || (!!orderName && !dirty)"
					:loading="busy === 'draft'"
					@click="saveDraft"
				/>
				<Button
					variant="solid"
					icon-left="lucide-send"
					label="Send order"
					:disabled="!ready || !!pricingError"
					:loading="busy === 'send'"
					@click="confirmingSend = true"
				/>
			</template>
		</template>

		<EmptyState
			v-if="!customer"
			icon="lucide-store"
			title="Switch to a customer account"
			description="Orders are placed for one of your customer accounts. Pick it at the top of the sidebar."
		/>

		<div v-else-if="loading && !form" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="unavailable"
			icon="lucide-shopping-cart"
			title="You cannot place this order"
			:description="unavailable"
		>
			<Button
				variant="subtle"
				label="Back to orders"
				@click="router.push({ name: 'SalesOrderList' })"
			/>
		</EmptyState>

		<div
			v-else-if="form"
			class="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start"
		>
			<div class="min-w-0 space-y-6">
				<section class="rounded-6 border p-4 sm:p-5">
					<h2 class="text-base font-medium text-ink-gray-8">Order details</h2>

					<div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
						<FormControl
							v-if="companies.length > 1"
							v-model="company"
							type="select"
							label="Ordering from"
							placeholder="Choose a company"
							:options="companies.map((name) => ({ label: name, value: name }))"
							:disabled="!!orderName || filledLines.length > 0"
							:description="
								orderName
									? 'To order from another company, start a new order.'
									: filledLines.length
									? 'Remove the items first to change company.'
									: 'Each company has its own items and prices.'
							"
							required
						/>
						<div v-else>
							<FormLabel label="Ordering from" />
							<p
								class="mt-1.5 flex h-7 items-center rounded-4 bg-surface-gray-1 px-2 text-base text-ink-gray-8"
							>
								{{ company }}
							</p>
						</div>

						<FormControl
							v-model="deliveryDate"
							type="date"
							label="Deliver by"
							:min="form.today"
							required
						/>
						<FormControl
							v-model="poNo"
							type="text"
							label="Your PO number"
							placeholder="Optional — your own reference"
							maxlength="140"
						/>
					</div>

					<fieldset class="mt-5">
						<legend class="flex w-full items-center justify-between gap-2">
							<FormLabel label="Deliver to" :required="addresses.length > 1" />
							<span v-if="addresses.length > 1" class="text-p-xs text-ink-gray-5">
								{{ addresses.length }} addresses on your account
							</span>
						</legend>

						<p
							v-if="!addresses.length"
							class="mt-2 flex items-start gap-2 rounded-6 border border-dashed p-3 text-p-sm text-ink-gray-6"
						>
							<i class="lucide-map-pin-off mt-0.5 size-4 shrink-0 text-ink-gray-5" />
							We do not have a delivery address for your account yet. Send the order
							and our team will confirm where to deliver.
						</p>

						<div v-else class="mt-2 grid gap-2 sm:grid-cols-2 2xl:grid-cols-3">
							<label
								v-for="option in addresses"
								:key="option.name"
								class="address-option flex cursor-pointer items-start gap-3 rounded-6 border p-3 transition-colors"
								:class="
									address === option.name
										? 'border-ink-gray-7 bg-surface-gray-2 ring-1 ring-ink-gray-7'
										: 'border-outline-gray-2 hover:border-outline-gray-3 hover:bg-surface-gray-1'
								"
							>
								<input
									v-model="address"
									type="radio"
									name="delivery-address"
									class="sr-only"
									:value="option.name"
								/>
								<i
									:class="
										address === option.name
											? 'lucide-circle-check-big text-ink-gray-9'
											: 'lucide-circle text-ink-gray-4'
									"
									class="mt-0.5 size-4 shrink-0"
									aria-hidden="true"
								/>
								<span class="min-w-0 flex-1">
									<span class="flex items-center gap-2">
										<span
											class="truncate text-base font-medium text-ink-gray-8"
										>
											{{ option.title }}
										</span>
										<Badge
											v-if="option.address_type"
											theme="gray"
											variant="subtle"
											size="sm"
											:label="option.address_type"
										/>
									</span>
									<span class="mt-0.5 block text-p-sm text-ink-gray-6">
										{{ option.lines || "No address lines on file" }}
									</span>
								</span>
							</label>
						</div>
					</fieldset>
				</section>

				<section class="rounded-6 border p-4 sm:p-5">
					<h2 class="text-base font-medium text-ink-gray-8">
						Items
						<span v-if="filledLines.length" class="text-ink-gray-5">
							({{ filledLines.length }})
						</span>
					</h2>

					<div class="mt-3 overflow-x-auto rounded-6 border">
						<div class="min-w-[910px]" role="table" aria-label="Order items">
							<div
								class="flex items-stretch bg-surface-gray-2 text-sm text-ink-gray-5"
								role="row"
							>
								<div
									class="flex w-10 shrink-0 items-center justify-center border-r"
									role="columnheader"
								>
									<Checkbox
										:model-value="allSelected"
										aria-label="Select all lines"
										@update:model-value="toggleAll(!!$event)"
									/>
								</div>
								<div
									class="flex w-10 shrink-0 items-center justify-center border-r"
									role="columnheader"
								>
									No
								</div>
								<div
									class="grid flex-1"
									:style="{ gridTemplateColumns: GRID_COLUMNS }"
								>
									<div class="border-r p-2" role="columnheader">
										Item <span class="text-ink-red-4">*</span>
									</div>
									<div class="border-r p-2" role="columnheader">Unit</div>
									<div class="border-r p-2 text-right" role="columnheader">
										Quantity <span class="text-ink-red-4">*</span>
									</div>
									<div class="border-r p-2 text-right" role="columnheader">
										Rate
									</div>
									<div class="p-2 text-right" role="columnheader">Amount</div>
								</div>
							</div>

							<div
								v-for="(line, index) in lines"
								:key="line.id"
								class="grid-row flex items-stretch border-t"
								:class="selected.has(line.id) ? 'bg-surface-gray-1' : ''"
								role="row"
							>
								<div
									class="flex w-10 shrink-0 items-center justify-center border-r"
								>
									<Checkbox
										:model-value="selected.has(line.id)"
										:aria-label="`Select line ${index + 1}`"
										@update:model-value="toggleLine(line, !!$event)"
									/>
								</div>
								<div
									class="flex w-10 shrink-0 items-center justify-center border-r text-sm text-ink-gray-7"
								>
									{{ index + 1 }}
								</div>
								<div
									class="grid flex-1"
									:style="{ gridTemplateColumns: GRID_COLUMNS }"
								>
									<div class="grid-cell min-w-0 border-r" role="cell">
										<ItemLink
											:model-value="line.item_code"
											:label="line.item_name"
											:customer="customer!"
											:company="company"
											:aria-label="`Item on line ${index + 1}`"
											@select="selectItem(line, $event)"
										/>
									</div>
									<div class="grid-cell min-w-0 border-r" role="cell">
										<Select
											v-if="line.uoms.length > 1"
											variant="ghost"
											:aria-label="`Unit on line ${index + 1}`"
											:options="
												line.uoms.map((option) => ({
													label: option.uom,
													value: option.uom,
												}))
											"
											:model-value="line.uom"
											@update:model-value="changeUom(line, String($event))"
										/>
										<span
											v-else
											class="flex h-full items-center px-2 text-sm text-ink-gray-7"
										>
											{{ line.uom || "—" }}
										</span>
									</div>
									<div class="grid-cell min-w-0 border-r" role="cell">
										<TextInput
											class="qty-input"
											type="number"
											variant="ghost"
											min="0"
											:disabled="!line.item_code"
											:aria-label="`Quantity on line ${index + 1}`"
											:model-value="line.qty"
											@update:model-value="setQty(line, $event)"
										/>
									</div>
									<div
										class="flex items-center justify-end whitespace-nowrap border-r px-3 text-sm tabular-nums text-ink-gray-7"
										role="cell"
									>
										<template v-if="pricedLine(line)">
											{{ money(pricedLine(line)!.rate, currency) }}
										</template>
										<span
											v-else-if="line.item_code"
											class="inline-block h-3.5 w-16 animate-pulse rounded bg-surface-gray-2"
										/>
									</div>
									<div
										class="flex items-center justify-end whitespace-nowrap px-3 text-sm font-medium tabular-nums text-ink-gray-8"
										role="cell"
									>
										<template v-if="pricedLine(line)">
											{{ money(pricedLine(line)!.amount, currency) }}
										</template>
										<span
											v-else-if="line.item_code"
											class="inline-block h-3.5 w-20 animate-pulse rounded bg-surface-gray-2"
										/>
									</div>
								</div>
							</div>
						</div>
					</div>

					<div class="mt-2 flex flex-wrap items-center gap-2">
						<Button
							v-if="selected.size"
							variant="solid"
							theme="red"
							icon-left="lucide-trash-2"
							:label="
								selected.size === 1
									? 'Delete line'
									: `Delete ${selected.size} lines`
							"
							@click="deleteSelected"
						/>
						<Button
							variant="subtle"
							icon-left="lucide-plus"
							label="Add row"
							:disabled="!company"
							@click="addRow"
						/>
						<span v-if="!company" class="text-p-sm text-ink-gray-5">
							Choose the company you are ordering from first.
						</span>
					</div>
				</section>
			</div>

			<aside class="space-y-4 lg:sticky lg:top-20">
				<section
					:class="ACCENTS[LOOKS.salesOrder.accent].panel"
					class="rounded-6 border p-4"
				>
					<div class="flex items-center justify-between">
						<h2 class="text-base font-medium text-ink-gray-8">Summary</h2>
						<span
							v-if="pricing"
							class="flex items-center gap-1.5 text-xs text-ink-gray-5"
						>
							<Spinner class="size-3" /> Updating prices
						</span>
					</div>

					<dl class="mt-3 space-y-2 text-p-sm tabular-nums">
						<div class="flex justify-between gap-4 text-ink-gray-7">
							<dt>Lines</dt>
							<dd>{{ filledLines.length }}</dd>
						</div>
						<div class="flex justify-between gap-4 text-ink-gray-7">
							<dt>Subtotal</dt>
							<dd class="whitespace-nowrap">
								{{
									priced && filledLines.length
										? money(priced.net_total, currency)
										: "—"
								}}
							</dd>
						</div>
						<div
							v-if="priced && priced.total_taxes"
							class="flex justify-between gap-4 text-ink-gray-7"
						>
							<dt>Taxes</dt>
							<dd class="whitespace-nowrap">
								{{ money(priced.total_taxes, currency) }}
							</dd>
						</div>
						<div
							class="flex justify-between gap-4 border-t pt-2 text-base font-medium text-ink-gray-8"
						>
							<dt>Total</dt>
							<dd class="whitespace-nowrap">
								{{
									priced && filledLines.length
										? money(priced.grand_total, currency)
										: "—"
								}}
							</dd>
						</div>
					</dl>

					<p class="mt-3 text-p-xs text-ink-gray-5">
						Prices come from your account's price list. Our team confirms every order
						before it is processed.
					</p>
				</section>

				<section
					class="rounded-6 border p-4"
					:class="
						missing.length
							? 'border-outline-amber-2 bg-surface-amber-1'
							: 'border-outline-green-2 bg-surface-green-1'
					"
					aria-live="polite"
				>
					<div class="flex items-start gap-2">
						<i
							:class="
								missing.length
									? 'lucide-info text-ink-amber-7'
									: 'lucide-circle-check-big text-ink-green-7'
							"
							class="mt-0.5 size-4 shrink-0"
							aria-hidden="true"
						/>
						<div class="min-w-0">
							<p class="text-base font-medium text-ink-gray-8">
								{{ missing.length ? "Before you send" : "Ready to send" }}
							</p>
							<p class="mt-0.5 text-p-sm text-ink-gray-6">
								{{
									missing.length
										? `${missing.length} of ${checklist.length} steps left.`
										: "Check the items and totals, then send your order."
								}}
							</p>
						</div>
					</div>

					<ul class="mt-3 space-y-1.5 text-p-sm">
						<li
							v-for="step in checklist"
							:key="step.label"
							class="flex items-center gap-2"
						>
							<i
								:class="
									step.done
										? 'lucide-circle-check text-ink-green-7'
										: 'lucide-circle text-ink-gray-4'
								"
								class="size-4 shrink-0"
								aria-hidden="true"
							/>
							<span
								:class="
									step.done ? 'text-ink-gray-5 line-through' : 'text-ink-gray-8'
								"
							>
								{{ step.label }}
							</span>
							<span class="sr-only">{{ step.done ? "done" : "to do" }}</span>
						</li>
					</ul>
				</section>

				<ErrorMessage v-if="pricingError" :message="pricingError" />
				<ErrorMessage v-if="errorMessage" :message="errorMessage" />
			</aside>
		</div>
		<Dialog
			v-model:open="confirmingSend"
			title="Send this order?"
			icon="lucide-send"
			theme="green"
			:message="`Your order comes to ${
				priced ? money(priced.grand_total, currency) : 'the total shown'
			}. Once sent you cannot change it — our team will review and confirm it.`"
			:actions="[
				{
					label: 'Send order',
					variant: 'solid',
					theme: 'green',
					loading: busy === 'send',
					onClick: send,
				},
			]"
		/>

		<Dialog
			v-model:open="confirmingDelete"
			title="Delete this draft?"
			icon="lucide-trash-2"
			theme="red"
			message="The draft and its items are removed. This cannot be undone."
			:actions="[
				{
					label: 'Delete draft',
					variant: 'solid',
					theme: 'red',
					loading: busy === 'delete',
					onClick: removeDraft,
				},
			]"
		/>
	</PageContainer>
</template>

<style scoped>
.grid-cell {
	display: flex;
	align-items: stretch;
}

.grid-cell > :deep(*) {
	flex: 1;
	min-width: 0;
}

.grid-cell :deep([data-slot="trigger"]) {
	display: flex;
	width: 100%;
	height: 100%;
	min-height: 40px;
	border-radius: 0;
	outline-offset: -2px;
}

.grid-cell :deep(input:not([type="checkbox"])) {
	height: 40px;
	border-radius: 0;
	outline-offset: -2px;
}

.grid-cell :deep(.qty-input input) {
	text-align: right;
}

.address-option:has(input:focus-visible) {
	outline: var(--focus-outline-default);
	outline-offset: 2px;
}
</style>
