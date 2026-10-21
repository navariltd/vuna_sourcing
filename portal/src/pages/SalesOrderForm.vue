<script setup lang="ts">
import { computed, onBeforeUnmount, ref, toRef, watch } from "vue";
import type { Ref } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import {
	Badge,
	BottomSheet,
	Button,
	Dialog,
	FormControl,
	Spinner,
	TextInput,
	Tooltip,
	toast,
} from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import OrderCart from "@/components/OrderCart.vue";
import OrderItemCard from "@/components/OrderItemCard.vue";
import { provideOrderDraft, useOrderDraft } from "@/composables/useOrderDraft";
import { errorText, fetchOrderCategories, fetchOrderableItems } from "@/data/orders";
import type { OrderCategory, OrderableItem } from "@/data/orders";
import { money } from "@/data/purchase";
import { isOk } from "@/types/api";
import { usePortalStore } from "@/stores/portal";
import { LOOKS } from "@/data/accents";

const props = defineProps<{ name?: string }>();

const PAGE_SIZE = 20;

const portal = usePortalStore();
const router = useRouter();

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty.name : null
);

const draft = useOrderDraft(customer, toRef(props, "name"));
provideOrderDraft(draft);

const { form, loading, unavailable, orderName, company, companies, lines, units, busy } = draft;

const categories = ref<OrderCategory[]>([]);
const category = ref<string | null>(null);
const search = ref("");
const items = ref<OrderableItem[]>([]);
const itemsCurrency = ref<string | null>(null);
const hasMore = ref(false);
const browsing = ref(false);
const browseError = ref<string | null>(null);
let browseRequest = 0;
let searchTimer: ReturnType<typeof setTimeout> | undefined;

const cartOpen = ref(false);
const confirmingSend = ref(false);
const confirmingDelete = ref(false);
const confirmingClear = ref(false);
const leaving = ref(false);

const VIEW_KEY = "vuna-sourcing:order-view";

function storedView(): "grid" | "list" {
	try {
		return localStorage.getItem(VIEW_KEY) === "list" ? "list" : "grid";
	} catch {
		return "grid";
	}
}

const view = ref<"grid" | "list">(storedView());

watch(view, (value) => {
	try {
		localStorage.setItem(VIEW_KEY, value);
	} catch {}
});

const allCount = computed(() => categories.value.reduce((total, row) => total + row.count, 0));

const tabs = computed(() => [
	{ name: null, label: "All", count: allCount.value },
	...categories.value.map((row) => ({ name: row.name, label: row.name, count: row.count })),
]);

async function loadCategories() {
	if (!customer.value || !company.value || !form.value) {
		categories.value = [];
		return;
	}

	try {
		const response = await fetchOrderCategories(customer.value, company.value);
		if (isOk(response)) categories.value = response.data;
	} catch {
		categories.value = [];
	}
}

async function browse(append = false) {
	if (!customer.value || !company.value || !form.value) {
		items.value = [];
		hasMore.value = false;
		return;
	}

	const request = ++browseRequest;
	browsing.value = true;
	browseError.value = null;

	try {
		const response = await fetchOrderableItems({
			customer: customer.value,
			company: company.value,
			search: search.value.trim() || null,
			item_group: category.value,
			start: append ? items.value.length : 0,
			limit: PAGE_SIZE,
		});
		if (request !== browseRequest) return;
		if (!isOk(response)) {
			browseError.value = response.message || "We could not load the items.";
			return;
		}
		items.value = append ? [...items.value, ...response.data.rows] : response.data.rows;
		itemsCurrency.value = response.data.currency;
		hasMore.value = response.data.has_more;
	} catch (error) {
		if (request === browseRequest)
			browseError.value = errorText(error, "We could not load the items.");
	} finally {
		if (request === browseRequest) browsing.value = false;
	}
}

watch([customer, company, form], () => {
	category.value = null;
	loadCategories();
	browse();
});

watch(category, () => browse());

watch(search, () => {
	clearTimeout(searchTimer);
	searchTimer = setTimeout(() => browse(), 250);
});

onBeforeUnmount(() => clearTimeout(searchTimer));

function observeVisibility(target: Ref<HTMLElement | null>, rootMargin: string) {
	const visible = ref(true);
	if (typeof IntersectionObserver === "undefined") return visible;

	const observer = new IntersectionObserver(
		(entries) => {
			visible.value = entries.some((entry) => entry.isIntersecting);
		},
		{ rootMargin }
	);
	watch(
		target,
		(element, previous) => {
			if (previous) observer.unobserve(previous);
			if (element) observer.observe(element);
		},
		{ immediate: true }
	);
	onBeforeUnmount(() => observer.disconnect());
	return visible;
}

const pageEnd = ref<HTMLElement | null>(null);
const nearPageEnd = observeVisibility(pageEnd, "0px 0px 600px 0px");

watch([nearPageEnd, browsing, hasMore], () => {
	if (!pageEnd.value || !nearPageEnd.value || browsing.value || !hasMore.value) return;
	if (browseError.value || !items.value.length) return;
	browse(true);
});

const pageTop = ref<HTMLElement | null>(null);
const nearPageTop = observeVisibility(pageTop, "800px 0px 0px 0px");
const showJumpToTop = computed(() => !!pageTop.value && !nearPageTop.value);

function scrollParent(element: HTMLElement | null): HTMLElement | null {
	for (let node = element?.parentElement; node; node = node.parentElement) {
		const overflow = getComputedStyle(node).overflowY;
		if (
			(overflow === "auto" || overflow === "scroll") &&
			node.scrollHeight > node.clientHeight
		)
			return node;
	}
	return null;
}

function jumpToTop() {
	const container = scrollParent(pageTop.value);
	if (container) container.scrollTo({ top: 0, behavior: "smooth" });
	else window.scrollTo({ top: 0, behavior: "smooth" });
}

const refreshing = ref(false);

async function refresh() {
	refreshing.value = true;
	draft.refreshPrices();
	try {
		await Promise.all([loadCategories(), browse()]);
		if (category.value && !categories.value.some((row) => row.name === category.value)) {
			category.value = null;
		}
	} finally {
		refreshing.value = false;
	}
}

const cartTotal = computed(() =>
	draft.priced.value && lines.value.length
		? money(draft.priced.value.grand_total, draft.currency.value)
		: null
);

const unitsLabel = computed(() => `${units.value} ${units.value === 1 ? "item" : "items"}`);

async function save() {
	const isNew = !orderName.value;
	const saved = await draft.saveDraft();
	if (saved && isNew && saved.name) {
		router.replace({ name: "SalesOrderEdit", params: { name: saved.name } });
	}
}

function askToSend() {
	cartOpen.value = false;
	confirmingSend.value = true;
}

const notice = computed(() => {
	if (!lines.value.length && !orderName.value) return null;
	if (orderName.value) {
		return {
			title: "This order has not been sent yet",
			text: draft.dirty.value
				? "Our team cannot see it until you send it. You also have changes that are not saved."
				: "Our team cannot see it until you send it. Check your cart, then tap Send order.",
		};
	}
	return {
		title: "Your order is not sent yet",
		text: "Tap Send order when you are done, or Save for later to keep it as a draft.",
	};
});

function sendFromNotice() {
	const nextStep = draft.missing.value[0]?.label;
	if (!nextStep && !draft.pricingError.value) {
		askToSend();
		return;
	}
	toast.info(
		nextStep ? `Before sending: ${nextStep.toLowerCase()}.` : draft.pricingError.value!
	);
	if (window.matchMedia?.("(max-width: 1023px)").matches) cartOpen.value = true;
}

function askToClear() {
	cartOpen.value = false;
	confirmingClear.value = true;
}

async function clearCart() {
	await draft.clearCart();
	confirmingClear.value = false;
}

const clearMessage = computed(() => {
	const count = `${lines.value.length} ${lines.value.length === 1 ? "item" : "items"}`;
	return orderName.value
		? `All ${count} are removed from draft ${orderName.value}. The draft stays, so you can add items again.`
		: `All ${count} are removed from your cart.`;
});

async function send() {
	const sent = await draft.send();
	confirmingSend.value = false;
	if (!sent?.name) {
		if (draft.errorMessage.value) cartOpen.value = true;
		return;
	}
	leaving.value = true;
	router.push({ name: "SalesOrderDetail", params: { name: sent.name } });
}

async function removeDraft() {
	const removed = await draft.removeDraft();
	confirmingDelete.value = false;
	if (!removed) return;
	leaving.value = true;
	router.push({ name: "SalesOrderList" });
}

onBeforeRouteLeave((to) => {
	if (leaving.value || !draft.dirty.value || !form.value) return true;
	if (to.name === "SalesOrderEdit" && to.params.name === orderName.value) return true;
	return window.confirm("Your cart has changes that are not saved. Leave anyway?");
});

const title = computed(() => (orderName.value ? `Draft ${orderName.value}` : "New order"));
</script>

<template>
	<PageContainer
		:look="LOOKS.salesOrder"
		fluid
		:title="title"
		:breadcrumbs="[
			{ label: 'Sales Orders', route: { name: 'SalesOrderList' } },
			{ label: orderName ? orderName : 'New order' },
		]"
	>
		<template #actions>
			<template v-if="form && !unavailable && orderName">
				<Badge theme="gray" variant="solid" size="lg" label="Draft" />
				<Button
					variant="subtle"
					theme="red"
					icon-left="lucide-trash-2"
					label="Delete draft"
					:disabled="!!busy"
					@click="confirmingDelete = true"
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

		<template v-else-if="form">
			<div ref="pageTop" />

			<div
				v-if="notice"
				class="mb-5 flex flex-col gap-3 rounded-8 border border-outline-amber-3 bg-surface-amber-1 p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4"
				role="status"
			>
				<div class="flex min-w-0 items-start gap-2.5">
					<i
						class="lucide-triangle-alert mt-0.5 size-5 shrink-0 text-ink-amber-7"
						aria-hidden="true"
					/>
					<div class="min-w-0">
						<p class="text-base font-semibold text-ink-gray-9">{{ notice.title }}</p>
						<p class="mt-0.5 text-p-sm text-ink-gray-7">{{ notice.text }}</p>
					</div>
				</div>
				<Button
					class="shrink-0"
					variant="solid"
					icon-left="lucide-send"
					label="Send order"
					:disabled="!!busy"
					@click="sendFromNotice"
				/>
			</div>

			<div class="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
				<div class="min-w-0">
					<div class="flex flex-col gap-3 sm:flex-row sm:items-end">
						<FormControl
							v-if="companies.length > 1"
							v-model="company"
							class="sm:w-64"
							type="select"
							label="Ordering from"
							placeholder="Choose a company"
							:options="companies.map((name) => ({ label: name, value: name }))"
							:disabled="!!orderName || lines.length > 0"
						/>
						<div class="flex min-w-0 flex-1 items-center gap-2">
							<TextInput
								v-model="search"
								class="min-w-0 flex-1"
								type="search"
								size="md"
								placeholder="Search items"
								aria-label="Search items"
								:disabled="!company"
							>
								<template #prefix>
									<i
										class="lucide-search size-4 text-ink-gray-5"
										aria-hidden="true"
									/>
								</template>
							</TextInput>
							<Tooltip text="Refresh items and prices">
								<Button
									size="md"
									variant="outline"
									aria-label="Refresh items and prices"
									:disabled="!company || refreshing"
									@click="refresh"
								>
									<template #icon>
										<i
											class="lucide-refresh-cw size-4"
											:class="refreshing ? 'animate-spin' : ''"
											aria-hidden="true"
										/>
									</template>
								</Button>
							</Tooltip>
							<div
								class="flex h-8 shrink-0 items-center rounded-6 bg-surface-gray-2 p-0.5"
								role="group"
								aria-label="Item layout"
							>
								<button
									v-for="option in [
									{ value: 'grid', icon: 'lucide-layout-grid', label: 'Grid view' },
									{ value: 'list', icon: 'lucide-list', label: 'List view' },
								] as const"
									:key="option.value"
									type="button"
									class="grid h-7 w-8 place-items-center rounded-5 transition-colors"
									:class="
										view === option.value
											? 'bg-surface-base text-ink-gray-9 shadow-sm'
											: 'text-ink-gray-6 hover:text-ink-gray-8'
									"
									:aria-label="option.label"
									:aria-pressed="view === option.value"
									:title="option.label"
									@click="view = option.value"
								>
									<i :class="option.icon" class="size-4" aria-hidden="true" />
								</button>
							</div>
						</div>
					</div>

					<p
						v-if="companies.length > 1 && (orderName || lines.length)"
						class="mt-1.5 text-p-xs text-ink-gray-5"
					>
						{{
							orderName
								? "To buy from another company, start a new order."
								: "Empty the cart to switch company."
						}}
					</p>

					<nav
						v-if="categories.length > 1"
						class="no-scrollbar -mx-4 mt-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0"
						aria-label="Item categories"
					>
						<button
							v-for="tab in tabs"
							:key="tab.name ?? '__all'"
							type="button"
							class="flex h-9 shrink-0 items-center gap-2 rounded-full border pl-3.5 pr-1.5 text-base font-medium transition-colors"
							:class="
								category === tab.name
									? 'border-outline-gray-9 bg-surface-gray-10 text-ink-base'
									: 'border-outline-gray-2 bg-surface-base text-ink-gray-8 hover:border-outline-gray-4 hover:bg-surface-gray-1'
							"
							:aria-pressed="category === tab.name"
							@click="category = tab.name"
						>
							{{ tab.label }}
							<span
								class="grid h-6 min-w-6 place-items-center rounded-full px-1.5 text-xs font-semibold tabular-nums"
								:class="
									category === tab.name
										? 'bg-surface-base text-ink-gray-9'
										: 'bg-surface-gray-10 text-ink-base'
								"
							>
								{{ tab.count }}
							</span>
						</button>
					</nav>

					<p v-if="!company" class="mt-8 text-center text-p-base text-ink-gray-5">
						Choose the company you are ordering from to see its items.
					</p>

					<p v-else-if="browseError" class="mt-8 text-center text-p-base text-ink-red-4">
						{{ browseError }}
					</p>

					<div
						v-else-if="browsing && !items.length"
						class="mt-4"
						:class="view === 'grid' ? 'item-grid' : 'flex flex-col gap-2'"
					>
						<div
							v-for="index in 8"
							:key="index"
							class="animate-pulse rounded-8 bg-surface-gray-2"
							:class="view === 'grid' ? 'h-56' : 'h-14'"
						/>
					</div>

					<EmptyState
						v-else-if="!items.length"
						class="mt-4"
						icon="lucide-package-search"
						:title="
							search.trim() ? 'No items match your search' : 'No items to order yet'
						"
						:description="
							search.trim()
								? 'Try a different name or clear the search.'
								: 'Items appear here once they have a price for your account.'
						"
					/>

					<template v-else>
						<div
							class="mt-4 transition-opacity"
							:class="[
								view === 'grid'
									? 'item-grid'
									: 'divide-y divide-outline-gray-1 overflow-hidden rounded-8 border',
								browsing ? 'opacity-60' : '',
							]"
						>
							<OrderItemCard
								v-for="item in items"
								:key="item.item_code"
								:item="item"
								:currency="itemsCurrency"
								:layout="view"
							/>
						</div>
						<div
							ref="pageEnd"
							class="mt-4 flex min-h-10 items-start justify-center pb-14"
						>
							<span
								v-if="browsing && hasMore"
								class="flex items-center gap-2 text-p-sm text-ink-gray-6"
							>
								<Spinner class="size-4" /> Loading more items
							</span>
							<Button
								v-else-if="hasMore"
								variant="subtle"
								label="Load more items"
								@click="browse(true)"
							/>
							<span
								v-else-if="items.length > PAGE_SIZE"
								class="text-p-sm text-ink-gray-5"
							>
								You have seen all {{ items.length }} items
							</span>
						</div>
					</template>

					<div class="pointer-events-none sticky bottom-[84px] z-10 h-0 lg:bottom-6">
						<Transition
							enter-from-class="translate-y-2 opacity-0"
							leave-to-class="translate-y-2 opacity-0"
							enter-active-class="transition duration-200"
							leave-active-class="transition duration-150"
						>
							<button
								v-if="showJumpToTop"
								type="button"
								class="pointer-events-auto absolute bottom-0 right-0 flex h-10 items-center gap-1.5 rounded-full border border-outline-gray-3 bg-surface-base px-4 text-base font-medium text-ink-gray-9 shadow-lg hover:bg-surface-gray-1"
								@click="jumpToTop"
							>
								<i class="lucide-arrow-up size-4" aria-hidden="true" />
								Back to top
							</button>
						</Transition>
					</div>
				</div>

				<aside
					class="hidden max-h-[calc(100dvh-6.5rem)] flex-col rounded-8 border bg-surface-base p-4 lg:sticky lg:top-6 lg:flex"
				>
					<h2
						class="mb-3 flex shrink-0 items-center justify-between gap-2 text-lg font-semibold text-ink-gray-9"
					>
						Your order
						<span
							v-if="lines.length"
							class="rounded-full bg-surface-gray-10 px-2.5 py-0.5 text-xs font-semibold text-ink-base"
						>
							{{ lines.length }} {{ lines.length === 1 ? "line" : "lines" }} ·
							{{ unitsLabel }}
						</span>
					</h2>
					<OrderCart class="flex-1" @save="save" @send="askToSend" @clear="askToClear" />
				</aside>

				<div class="sticky bottom-3 z-10 lg:hidden">
					<button
						type="button"
						class="flex h-14 w-full items-center justify-between gap-3 rounded-full pl-2 pr-2 shadow-[0_8px_24px_rgba(0,0,0,0.25)] transition-transform active:scale-[0.98]"
						:class="
							units
								? 'bg-surface-gray-10 text-ink-base'
								: 'border border-outline-gray-3 bg-surface-base text-ink-gray-8'
						"
						:aria-label="units ? `View cart, ${unitsLabel}` : 'View cart, empty'"
						@click="cartOpen = true"
					>
						<span class="flex min-w-0 items-center gap-2.5">
							<span
								class="relative grid size-10 shrink-0 place-items-center rounded-full"
								:class="
									units
										? 'bg-surface-base text-ink-gray-9'
										: 'bg-surface-gray-2 text-ink-gray-7'
								"
							>
								<i class="lucide-shopping-basket size-5" aria-hidden="true" />
								<span
									v-if="lines.length"
									class="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-surface-gray-10 px-1 text-[11px] font-bold tabular-nums text-ink-base shadow-[0_0_0_2px_var(--surface-base)]"
								>
									{{ lines.length }}
								</span>
							</span>
							<span class="flex min-w-0 flex-col items-start leading-tight">
								<span class="text-base font-semibold">
									{{ units ? "View cart" : "Your cart is empty" }}
								</span>
								<span v-if="units" class="text-xs opacity-90">{{
									unitsLabel
								}}</span>
							</span>
						</span>
						<span
							v-if="units"
							class="flex h-10 shrink-0 items-center gap-1.5 rounded-full bg-surface-base px-4 text-base font-bold tabular-nums text-ink-gray-9"
						>
							<Spinner v-if="draft.pricing.value" class="size-3.5" />
							<template v-else>{{ cartTotal ?? "—" }}</template>
							<i class="lucide-chevron-up size-4" aria-hidden="true" />
						</span>
						<i v-else class="lucide-chevron-up mr-3 size-4" aria-hidden="true" />
					</button>
				</div>
			</div>
		</template>

		<BottomSheet v-model:open="cartOpen" title="Your order">
			<div class="px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
				<OrderCart @save="save" @send="askToSend" @clear="askToClear" />
			</div>
		</BottomSheet>

		<Dialog
			v-model:open="confirmingSend"
			title="Send this order?"
			icon="lucide-send"
			:message="`Your order comes to ${
				cartTotal ?? 'the total shown'
			}. Once sent you cannot change it. Our team will review and confirm it.`"
			:actions="[
				{
					label: 'Send order',
					variant: 'solid',
					loading: busy === 'send',
					onClick: send,
				},
			]"
		/>

		<Dialog
			v-model:open="confirmingClear"
			title="Clear your cart?"
			icon="lucide-trash-2"
			theme="red"
			:message="clearMessage"
			:actions="[
				{
					label: 'Clear cart',
					variant: 'solid',
					theme: 'red',
					loading: busy === 'clear',
					onClick: clearCart,
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
.item-grid {
	display: grid;
	gap: 0.75rem;
	grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (min-width: 640px) {
	.item-grid {
		grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
	}
}

.no-scrollbar {
	scrollbar-width: none;
}

.no-scrollbar::-webkit-scrollbar {
	display: none;
}
</style>
