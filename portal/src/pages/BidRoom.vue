<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
	Badge,
	Button,
	Dialog,
	ErrorMessage,
	FormControl,
	Spinner,
	Tooltip,
	toast,
} from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import {
	RFQ_STATUS_THEME,
	createOpenBidsResource,
	createRfqResource,
	sendQuote,
} from "@/data/rfq";
import type { OpenBidBoard, Rfq } from "@/data/rfq";
import { usePortalStore } from "@/stores/portal";
import { useCountdown } from "@/composables/useCountdown";
import { useRealtime } from "@/composables/useRealtime";
import { ACCENTS, LOOKS } from "@/data/accents";

const REFRESH_SPREAD_MS = [300, 800];

const props = defineProps<{ name: string }>();

const portal = usePortalStore();
const router = useRouter();

const request = createRfqResource();
const bids = createOpenBidsResource();

const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);
const rfq = computed<Rfq | null>(() => request.data ?? null);
const board = computed<OpenBidBoard | null>(() => bids.data?.data ?? null);
const yours = computed(() => board.value?.bids.find((bid) => bid.is_you) ?? null);
const leader = computed(() => board.value?.bids[0] ?? null);
const leading = computed(() => yours.value?.rank === 1);

const countdown = useCountdown(() => rfq.value?.closes_at);
const live = computed(() => rfq.value?.status === "Bidding" && !countdown.ended.value);

const prices = reactive<Record<string, number | null>>({});
const validTill = ref<string | null>(null);
const confirming = ref(false);
const placing = ref(false);
const errorMessage = ref<string | null>(null);

function fill(doc: Rfq) {
	for (const item of doc.items) prices[item.name] = item.rate ?? null;
	validTill.value = doc.quote?.valid_till ?? null;
}

async function loadBoard() {
	if (!supplier.value) return;
	const previousRank = yours.value?.rank;
	await bids.fetch({ name: props.name, supplier: supplier.value });
	if (previousRank === 1 && yours.value && yours.value.rank > 1) {
		toast.warning(`You have been outbid on ${props.name}`, {
			description: `You are now ranked #${yours.value.rank}.`,
		});
	}
}

async function load() {
	if (!supplier.value) return;
	const doc = (await request.fetch({ name: props.name, supplier: supplier.value })) as Rfq;
	if (!doc) return;

	if (
		!doc.open_bid ||
		!["Bidding", "Submitted", "Awarded", "Not Selected"].includes(doc.status)
	) {
		router.replace({ name: "RfqDetail", params: { name: props.name } });
		return;
	}

	fill(doc);
	await loadBoard();
}

watch([supplier, () => props.name], load, { immediate: true });

let scheduled: ReturnType<typeof setTimeout> | null = null;

function scheduleRefresh() {
	if (scheduled) return;
	const [min, max] = REFRESH_SPREAD_MS;
	scheduled = setTimeout(() => {
		scheduled = null;
		loadBoard();
	}, min + Math.random() * (max - min));
}

useRealtime<{ rfq: string }>(
	"open_bid_placed",
	(data) => {
		if (data.rfq === props.name) scheduleRefresh();
	},
	() => {
		if (live.value) loadBoard();
	}
);

onBeforeUnmount(() => {
	if (scheduled) clearTimeout(scheduled);
});

watch(countdown.ended, (ended) => {
	if (ended && rfq.value?.status === "Bidding") load();
});

const currentTotal = computed(() =>
	(rfq.value?.items ?? []).reduce((sum, item) => sum + (item.rate ?? 0) * item.qty, 0)
);
const newTotal = computed(() =>
	(rfq.value?.items ?? []).reduce((sum, item) => sum + (prices[item.name] ?? 0) * item.qty, 0)
);
const change = computed(() => newTotal.value - currentTotal.value);
const changed = computed(() =>
	(rfq.value?.items ?? []).some((item) => (prices[item.name] ?? null) !== (item.rate ?? null))
);
const complete = computed(() =>
	(rfq.value?.items ?? []).every((item) => (prices[item.name] ?? 0) > 0)
);
const blocked = computed(() => {
	if (!complete.value) return "Enter a price for every item.";
	if (!changed.value) return "Change at least one price to place a new bid.";
	if (!validTill.value) return "Set how long your prices stay valid.";
	return null;
});
const sameCurrency = computed(
	() => !rfq.value?.quote?.currency || rfq.value.quote.currency === board.value?.currency
);

function matchLowest() {
	if (!board.value) return;
	for (const item of rfq.value?.items ?? []) {
		const lowest = board.value.lowest_rates[item.name];
		if (lowest) prices[item.name] = lowest;
	}
}

async function placeBid() {
	if (!rfq.value || !supplier.value) return;

	errorMessage.value = null;
	placing.value = true;
	try {
		const updated = (await sendQuote({
			name: rfq.value.name,
			supplier: supplier.value,
			items: rfq.value.items.map((item) => ({
				rfq_item: item.name,
				rate: prices[item.name] ?? null,
				lead_time_days: item.lead_time_days,
			})),
			quotation_number: rfq.value.quote?.quotation_number ?? null,
			valid_till: validTill.value,
		})) as Rfq;
		request.setData(updated);
		fill(updated);
		confirming.value = false;
		await loadBoard();
		toast.success("Bid placed", {
			description: yours.value
				? `You are ranked #${yours.value.rank} of ${board.value?.bidders}.`
				: undefined,
		});
	} catch (error: any) {
		errorMessage.value =
			error?.messages?.[0] || error?.message || "We could not place your bid.";
		confirming.value = false;
	} finally {
		placing.value = false;
	}
}

function money(value: number | null | undefined) {
	if (value == null) return "—";
	return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function signed(value: number) {
	return `${value > 0 ? "+" : value < 0 ? "−" : ""}${money(Math.abs(value))}`;
}

function formatDateTime(value: string | null | undefined) {
	if (!value) return "—";
	return new Date(value).toLocaleString(undefined, {
		day: "numeric",
		month: "short",
		hour: "2-digit",
		minute: "2-digit",
	});
}
</script>

<template>
	<PageContainer
		:look="LOOKS.rfq"
		wide
		title="Bid room"
		:breadcrumbs="[
			{ label: 'Request for Quotation', route: { name: 'RfqList' } },
			{ label: name, route: { name: 'RfqDetail', params: { name } } },
			{ label: 'Bid room' },
		]"
	>
		<template #actions>
			<Badge
				v-if="rfq"
				:theme="RFQ_STATUS_THEME[rfq.status]"
				variant="subtle"
				:label="live ? 'Bidding open' : 'Bidding closed'"
			/>
			<Button
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh bids"
				:loading="bids.loading"
				@click="loadBoard"
			/>
			<Button
				variant="subtle"
				icon-left="lucide-file-text"
				label="Request details"
				:route="{ name: 'RfqDetail', params: { name } }"
			/>
		</template>

		<EmptyState
			v-if="!supplier"
			icon="lucide-truck"
			title="Switch to a supplier account"
			description="This request belongs to one of your supplier accounts. Pick it at the top of the sidebar."
		/>

		<div v-else-if="!rfq || (!board && bids.loading)" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="request.error || bids.error"
			icon="lucide-gavel"
			title="We cannot open this bid room"
			description="Place your first bid from the request to join the bidding."
		>
			<Button
				variant="subtle"
				label="Back to the request"
				:route="{ name: 'RfqDetail', params: { name } }"
			/>
		</EmptyState>

		<div v-else-if="board" class="space-y-6">
			<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
				<div :class="ACCENTS[LOOKS.rfq.accent].panel" class="rounded-6 border p-4">
					<p class="text-xs uppercase tracking-wide text-ink-gray-5">
						{{ live ? "Bidding closes in" : "Bidding closed" }}
					</p>
					<p
						class="mt-1 font-mono text-2xl font-semibold tabular-nums"
						:class="
							live && countdown.urgent.value ? 'text-ink-red-6' : 'text-ink-gray-9'
						"
					>
						{{ live ? countdown.label.value : "Closed" }}
					</p>
					<p class="mt-1 text-p-sm text-ink-gray-5">
						{{ formatDateTime(rfq.closes_at) }}
					</p>
				</div>

				<div
					class="rounded-6 border p-4"
					:class="
						leading
							? 'border-outline-green-2 bg-surface-green-1'
							: 'border-outline-amber-2 bg-surface-amber-1'
					"
				>
					<p class="text-xs uppercase tracking-wide text-ink-gray-5">Your rank</p>
					<p class="mt-1 text-2xl font-semibold text-ink-gray-9">
						#{{ yours?.rank ?? "—" }}
						<span class="text-base font-normal text-ink-gray-5"
							>of {{ board.bidders }}</span
						>
					</p>
					<p
						class="mt-1 text-p-sm font-semibold"
						:class="leading ? 'text-ink-green-7' : 'text-ink-amber-7'"
					>
						<template v-if="leading">
							{{ live ? "You are leading" : "You had the lowest bid" }}
						</template>
						<template v-else>
							{{ live ? "Outbid" : "Not the lowest" }} by
							{{ money((yours?.total ?? 0) - (leader?.total ?? 0)) }}
						</template>
					</p>
				</div>

				<div class="rounded-6 border p-4">
					<p class="text-xs uppercase tracking-wide text-ink-gray-5">Your bid</p>
					<p class="mt-1 text-2xl font-semibold text-ink-gray-9">
						{{ money(yours?.total) }}
					</p>
					<p class="mt-1 text-p-sm text-ink-gray-5">
						{{ board.your_bids.length }}
						{{ board.your_bids.length === 1 ? "bid" : "bids" }} placed
					</p>
				</div>

				<div class="rounded-6 border p-4">
					<p class="text-xs uppercase tracking-wide text-ink-gray-5">Lowest bid</p>
					<p class="mt-1 text-2xl font-semibold text-ink-gray-9">
						{{ money(board.lowest) }}
					</p>
					<p class="mt-1 text-p-sm text-ink-gray-5">
						{{ board.bidders }} {{ board.bidders === 1 ? "bidder" : "bidders" }} ·
						{{ board.currency }}
					</p>
				</div>
			</div>

			<div class="grid gap-6 lg:grid-cols-5">
				<section class="overflow-hidden rounded-6 border lg:col-span-3">
					<header
						class="flex flex-wrap items-center justify-between gap-2 border-b bg-surface-gray-1 px-4 py-3"
					>
						<div>
							<p class="text-base font-medium text-ink-gray-8">
								{{ live ? "Place a new bid" : "Your final bid" }}
							</p>
							<p class="text-p-sm text-ink-gray-5">
								{{
									live
										? "Your new bid replaces your current one. Other bidders only see your total and rank."
										: "Bidding has closed. The buyer is reviewing the latest bid from each bidder."
								}}
							</p>
						</div>
						<Button
							v-if="live && sameCurrency"
							variant="solid"
							icon-left="lucide-arrow-down-to-line"
							label="Take Lead"
							@click="matchLowest"
						/>
					</header>

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
								<p class="text-p-sm text-ink-gray-5">
									{{ item.qty }} {{ item.uom }}
								</p>
							</div>

							<div class="flex gap-4 text-p-sm sm:col-span-4">
								<div>
									<p class="text-xs text-ink-gray-5">Lowest</p>
									<p
										class="font-semibold"
										:class="
											board.lowest_rates[item.name] ===
											yours?.rates[item.name]
												? 'text-ink-green-7'
												: 'text-ink-gray-9'
										"
									>
										{{ money(board.lowest_rates[item.name]) }}
									</p>
								</div>
								<div>
									<p class="text-xs text-ink-gray-5">Yours now</p>
									<p class="font-semibold text-ink-gray-9">
										{{ money(item.rate) }}
									</p>
								</div>
							</div>

							<FormControl
								v-if="live"
								class="sm:col-span-3"
								type="number"
								size="sm"
								placeholder="New price"
								:model-value="prices[item.name] ?? undefined"
								@update:model-value="
									prices[item.name] = $event === '' ? null : Number($event)
								"
							/>
						</div>
					</div>

					<footer v-if="live" class="space-y-4 border-t bg-surface-gray-1 px-4 py-3">
						<div class="flex flex-wrap items-end justify-between gap-4">
							<div>
								<p class="text-xs uppercase tracking-wide text-ink-gray-5">
									New total
								</p>
								<p class="text-xl font-semibold text-ink-gray-9">
									{{ money(newTotal) }}
								</p>
								<p
									v-if="changed"
									class="text-p-sm font-semibold"
									:class="change <= 0 ? 'text-ink-green-7' : 'text-ink-red-6'"
								>
									{{ signed(change) }} against your current bid
								</p>
								<p
									v-if="!leading && leader && sameCurrency"
									class="text-p-sm font-medium text-ink-gray-7"
								>
									To lead, bid below {{ money(leader.total) }}
								</p>
							</div>

							<FormControl
								v-model="validTill"
								class="w-44"
								type="date"
								label="Prices valid until"
							/>
						</div>

						<ErrorMessage v-if="errorMessage" :message="errorMessage" />

						<div class="flex justify-end">
							<Tooltip :text="blocked ?? undefined" :disabled="!blocked">
								<span class="inline-flex">
									<Button
										variant="solid"
										theme="green"
										icon-left="lucide-gavel"
										label="Place bid"
										:disabled="!!blocked"
										@click="confirming = true"
									/>
								</span>
							</Tooltip>
						</div>
					</footer>
				</section>

				<div class="space-y-6 lg:col-span-2">
					<section class="overflow-hidden rounded-6 border">
						<header class="border-b bg-surface-gray-1 px-4 py-3">
							<p class="text-base font-medium text-ink-gray-8">Leaderboard</p>
							<p class="text-p-sm text-ink-gray-5">
								{{ live ? "Updates live as bids come in." : "Final standings." }}
							</p>
						</header>
						<ol class="divide-y">
							<li
								v-for="bid in board.bids"
								:key="bid.alias"
								class="flex items-center gap-3 px-4 py-2"
								:class="bid.is_you ? 'bg-surface-green-1' : ''"
							>
								<span
									class="flex size-7 shrink-0 items-center justify-center rounded-full text-p-sm font-semibold"
									:class="
										bid.rank === 1
											? 'bg-surface-green-3 text-ink-base'
											: 'bg-surface-gray-2 text-ink-gray-7'
									"
								>
									{{ bid.rank }}
								</span>
								<div class="min-w-0 flex-1">
									<p class="truncate text-p-sm font-semibold text-ink-gray-9">
										{{ bid.alias }}
										<span
											v-if="bid.is_you"
											class="font-semibold text-ink-green-7"
											>· you</span
										>
									</p>
									<p class="text-xs text-ink-gray-5">
										{{ formatDateTime(bid.bid_at) }}
										<template v-if="bid.revisions > 1">
											· {{ bid.revisions }} bids
										</template>
									</p>
								</div>
								<div class="text-right">
									<p class="text-p-sm font-semibold text-ink-gray-9">
										{{ money(bid.total) }}
									</p>
									<p
										v-if="bid.rank > 1 && leader"
										class="text-xs font-medium text-ink-red-6"
									>
										+{{ money(bid.total - leader.total) }}
									</p>
								</div>
							</li>
						</ol>
					</section>

					<section class="overflow-hidden rounded-6 border">
						<header
							class="flex items-center justify-between border-b bg-surface-gray-1 px-4 py-3"
						>
							<p class="text-base font-medium text-ink-gray-8">Your bids</p>
							<span class="text-p-sm text-ink-gray-6">{{
								board.your_bids.length
							}}</span>
						</header>
						<ol class="max-h-64 divide-y overflow-y-auto overscroll-contain">
							<li
								v-for="bid in board.your_bids"
								:key="bid.name"
								class="flex items-center justify-between gap-3 px-4 py-2"
							>
								<div>
									<p class="text-p-sm font-semibold text-ink-gray-9">
										{{ money(bid.total) }}
									</p>
									<p class="text-xs text-ink-gray-5">
										{{ formatDateTime(bid.bid_at) }}
									</p>
								</div>
								<Badge
									:theme="bid.live ? 'green' : 'gray'"
									variant="subtle"
									:label="bid.live ? 'Current' : 'Replaced'"
								/>
							</li>
						</ol>
					</section>
				</div>
			</div>
		</div>

		<Dialog
			v-model:open="confirming"
			title="Place this bid?"
			icon="lucide-gavel"
			:message="`Your new total is ${money(
				newTotal
			)}. It replaces your current bid of ${money(currentTotal)} and cannot be withdrawn.`"
			:actions="[
				{
					label: 'Place bid',
					variant: 'solid',
					theme: 'green',
					loading: placing,
					onClick: placeBid,
				},
			]"
		/>
	</PageContainer>
</template>
