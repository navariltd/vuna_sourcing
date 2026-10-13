<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { createLiveBidsResource, rfqRoute } from "@/data/rfq";
import type { LiveBid } from "@/data/rfq";
import type { ApiResponse } from "@/types/api";
import { usePortalStore } from "@/stores/portal";
import { useRealtime } from "@/composables/useRealtime";
import { useIsMobile } from "@/composables/useViewport";
import LiveBidRow from "@/components/LiveBidRow.vue";

const POLL_MS = 60_000;
const REFRESH_SPREAD_MS = [300, 800];
const EDGE_PX = 12;
const DRAG_THRESHOLD_PX = 4;
const MAX_ROWS = 3;
const STORAGE_KEY = "vuna-sourcing:live-bid-dock";
const ROUTES_SHOWING_ONE_RFQ = ["BidRoom", "RfqDetail"];

interface DockPlacement {
	right: number;
	bottom: number;
	collapsed: boolean;
}

function recall(): Partial<DockPlacement> {
	try {
		return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
	} catch {
		return {};
	}
}

const portal = usePortalStore();
const route = useRoute();
const router = useRouter();
const isMobile = useIsMobile();

const live = createLiveBidsResource();

const supplier = computed(() =>
	portal.activeParty?.party_type === "Supplier" ? portal.activeParty.name : null
);
const bids = computed<LiveBid[]>(() => (live.data as ApiResponse<LiveBid[]> | null)?.data ?? []);
const rfqOnScreen = computed(() =>
	ROUTES_SHOWING_ONE_RFQ.includes(String(route.name)) ? String(route.params.name) : null
);
const shown = computed(() => bids.value.filter((bid) => bid.name !== rfqOnScreen.value));
const visible = computed(() => !!supplier.value && shown.value.length > 0);
const behind = computed(() => shown.value.some((bid) => bid.has_bid && bid.rank !== 1));

const saved = recall();
const right = ref(saved.right ?? 24);
const bottom = ref(saved.bottom ?? (isMobile.value ? 88 : 24));
const collapsed = ref(saved.collapsed ?? false);
const dock = ref<HTMLElement | null>(null);

function remember() {
	try {
		window.localStorage.setItem(
			STORAGE_KEY,
			JSON.stringify({
				right: right.value,
				bottom: bottom.value,
				collapsed: collapsed.value,
			})
		);
	} catch {
		return;
	}
}

function keepOnScreen() {
	const element = dock.value;
	if (!element) return;
	const maxRight = Math.max(window.innerWidth - element.offsetWidth - EDGE_PX, EDGE_PX);
	const maxBottom = Math.max(window.innerHeight - element.offsetHeight - EDGE_PX, EDGE_PX);
	right.value = Math.min(Math.max(right.value, EDGE_PX), maxRight);
	bottom.value = Math.min(Math.max(bottom.value, EDGE_PX), maxBottom);
}

let drag: {
	pointer: number;
	x: number;
	y: number;
	right: number;
	bottom: number;
	moved: boolean;
} | null = null;
let swallowClick = false;
const dragging = ref(false);

function startDrag(event: PointerEvent) {
	if (event.button !== 0) return;
	drag = {
		pointer: event.pointerId,
		x: event.clientX,
		y: event.clientY,
		right: right.value,
		bottom: bottom.value,
		moved: false,
	};
	(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function moveDrag(event: PointerEvent) {
	if (!drag || event.pointerId !== drag.pointer) return;
	const dx = event.clientX - drag.x;
	const dy = event.clientY - drag.y;
	if (!drag.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return;

	drag.moved = true;
	dragging.value = true;
	right.value = drag.right - dx;
	bottom.value = drag.bottom - dy;
	keepOnScreen();
}

function endDrag(event: PointerEvent) {
	if (!drag || event.pointerId !== drag.pointer) return;
	swallowClick = drag.moved;
	drag = null;
	dragging.value = false;
	if (swallowClick) remember();
}

function clicked(): boolean {
	if (!swallowClick) return true;
	swallowClick = false;
	return false;
}

function setCollapsed(value: boolean) {
	collapsed.value = value;
	remember();
	nextTick(keepOnScreen);
}

function expand() {
	if (clicked()) setCollapsed(false);
}

function collapse() {
	if (clicked()) setCollapsed(true);
}

function open(bid: LiveBid) {
	router.push(rfqRoute(bid));
}

function refresh() {
	if (!supplier.value) return;
	live.fetch({ supplier: supplier.value });
}

let scheduled: ReturnType<typeof setTimeout> | null = null;

function scheduleRefresh() {
	if (scheduled) return;
	const [min, max] = REFRESH_SPREAD_MS;
	scheduled = setTimeout(() => {
		scheduled = null;
		refresh();
	}, min + Math.random() * (max - min));
}

useRealtime<{ rfq: string }>(
	"open_bid_placed",
	(data) => {
		if (bids.value.some((bid) => bid.name === data.rfq)) scheduleRefresh();
	},
	refresh
);

watch(supplier, refresh, { immediate: true });
watch(() => route.name, refresh);
watch(visible, (now) => now && nextTick(keepOnScreen));

let poll: ReturnType<typeof setInterval> | null = null;

function pollWhileVisible() {
	if (!document.hidden) refresh();
}

onMounted(() => {
	poll = setInterval(pollWhileVisible, POLL_MS);
	window.addEventListener("resize", keepOnScreen);
	document.addEventListener("visibilitychange", pollWhileVisible);
});

onBeforeUnmount(() => {
	if (poll) clearInterval(poll);
	if (scheduled) clearTimeout(scheduled);
	window.removeEventListener("resize", keepOnScreen);
	document.removeEventListener("visibilitychange", pollWhileVisible);
});
</script>

<template>
	<Teleport to="body">
		<div
			v-if="visible"
			ref="dock"
			class="fixed z-40 select-none"
			:style="{ right: `${right}px`, bottom: `${bottom}px` }"
		>
			<button
				v-if="collapsed"
				type="button"
				class="flex touch-none items-center gap-2 rounded-full bg-surface-gray-9 px-3 py-2 text-sm font-medium text-ink-gray-1 shadow-lg"
				:class="dragging ? 'cursor-grabbing' : 'cursor-grab'"
				:aria-label="`${shown.length} live ${shown.length === 1 ? 'bid' : 'bids'}. Show`"
				@pointerdown="startDrag"
				@pointermove="moveDrag"
				@pointerup="endDrag"
				@pointercancel="endDrag"
				@click="expand"
			>
				<span class="relative flex size-2" aria-hidden="true">
					<span
						class="absolute inline-flex size-full animate-ping rounded-full bg-surface-red-6 opacity-75"
					/>
					<span class="relative inline-flex size-2 rounded-full bg-surface-red-6" />
				</span>
				<span>Live {{ shown.length === 1 ? "bid" : `bids · ${shown.length}` }}</span>
				<i
					v-if="behind"
					class="lucide-trending-down size-4 text-ink-red-4"
					aria-hidden="true"
				/>
			</button>

			<section
				v-else
				class="w-72 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-7 border border-outline-gray-2 bg-surface-base shadow-lg"
				aria-label="Live bids"
			>
				<header
					class="flex touch-none items-center gap-2 border-b border-outline-gray-2 py-2 pl-3 pr-1.5"
					:class="dragging ? 'cursor-grabbing' : 'cursor-grab'"
					@pointerdown="startDrag"
					@pointermove="moveDrag"
					@pointerup="endDrag"
					@pointercancel="endDrag"
				>
					<span class="relative flex size-2" aria-hidden="true">
						<span
							class="absolute inline-flex size-full animate-ping rounded-full bg-surface-red-6 opacity-75"
						/>
						<span class="relative inline-flex size-2 rounded-full bg-surface-red-6" />
					</span>
					<span class="flex-1 text-sm font-medium text-ink-gray-8">
						Live {{ shown.length === 1 ? "bid" : "bids" }}
					</span>
					<i class="lucide-grip-horizontal size-4 text-ink-gray-4" aria-hidden="true" />
					<button
						type="button"
						class="grid size-7 place-items-center rounded-5 text-ink-gray-5 hover:bg-surface-gray-2"
						aria-label="Minimise live bids"
						@pointerdown.stop
						@click="collapse"
					>
						<i class="lucide-minus size-4" aria-hidden="true" />
					</button>
				</header>

				<div class="p-1">
					<LiveBidRow
						v-for="bid in shown.slice(0, MAX_ROWS)"
						:key="bid.name"
						:bid="bid"
						@open="open"
						@ended="refresh"
					/>
					<RouterLink
						v-if="shown.length > MAX_ROWS"
						:to="{ name: 'RfqList' }"
						class="block rounded-6 px-2 py-1.5 text-center text-xs text-ink-gray-5 hover:bg-surface-gray-2"
					>
						View all {{ shown.length }} live bids
					</RouterLink>
				</div>
			</section>
		</div>
	</Teleport>
</template>
