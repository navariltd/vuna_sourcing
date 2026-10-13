<script setup lang="ts">
import { computed, watch } from "vue";
import { useCountdown } from "@/composables/useCountdown";
import type { LiveBid } from "@/data/rfq";

const props = defineProps<{ bid: LiveBid }>();
const emit = defineEmits<{ open: [bid: LiveBid]; ended: [] }>();

const countdown = useCountdown(() => props.bid.closes_at);

watch(countdown.ended, (ended) => {
	if (ended) emit("ended");
});

const standing = computed(() => {
	const { has_bid, rank, bidders } = props.bid;
	if (!has_bid) return "You have not bid yet";
	if (rank === 1) return `You lead · ${bidders} ${bidders === 1 ? "bidder" : "bidders"}`;
	return `You are #${rank} of ${bidders}`;
});
</script>

<template>
	<button
		type="button"
		class="flex w-full items-center gap-3 rounded-6 px-2 py-2 text-left hover:bg-surface-gray-2 focus-visible:bg-surface-gray-2 focus-visible:outline-none"
		@click="emit('open', bid)"
	>
		<span class="min-w-0 flex-1">
			<span class="block truncate text-sm font-medium text-ink-gray-8">{{ bid.name }}</span>
			<span
				class="block truncate text-xs"
				:class="bid.has_bid && bid.rank !== 1 ? 'text-ink-amber-7' : 'text-ink-gray-5'"
			>
				{{ standing }}
			</span>
		</span>
		<span
			class="shrink-0 font-mono text-xs tabular-nums"
			:class="countdown.urgent.value ? 'text-ink-red-6' : 'text-ink-gray-7'"
		>
			{{ countdown.label.value }}
		</span>
		<i class="lucide-chevron-right size-4 shrink-0 text-ink-gray-4" aria-hidden="true" />
	</button>
</template>
