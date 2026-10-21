<script setup lang="ts">
import { computed } from "vue";
import { Button } from "frappe-ui";
import QtyStepper from "@/components/QtyStepper.vue";
import { injectOrderDraft } from "@/composables/useOrderDraft";
import type { OrderableItem } from "@/data/orders";
import { money } from "@/data/purchase";

const props = defineProps<{
	item: OrderableItem;
	currency: string | null;
	layout: "grid" | "list";
}>();

const draft = injectOrderDraft();

const line = computed(() => draft.lineFor(props.item.item_code, props.item.uom));

const initials = computed(() =>
	props.item.item_name
		.replace(/[^\p{L}\p{N}\s]/gu, "")
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((word) => word[0]!.toUpperCase())
		.join("")
);
</script>

<template>
	<article
		v-if="layout === 'grid'"
		class="relative flex min-w-0 flex-col overflow-hidden rounded-8 border bg-surface-base transition-[border-color,box-shadow]"
		:class="
			line
				? 'border-outline-gray-7 shadow-[0_0_0_1px_var(--outline-gray-7)]'
				: 'border-outline-gray-2 hover:border-outline-gray-4'
		"
	>
		<div class="relative aspect-[3/2] bg-surface-gray-1">
			<img
				v-if="item.image"
				:src="item.image"
				:alt="item.item_name"
				loading="lazy"
				class="size-full object-cover"
			/>
			<div
				v-else
				class="grid size-full place-items-center text-xl font-semibold text-ink-gray-4"
				aria-hidden="true"
			>
				{{ initials }}
			</div>
			<span
				v-if="line"
				class="absolute right-2 top-2 flex items-center gap-1 rounded-full bg-surface-gray-10 py-1 pl-1.5 pr-2.5 text-xs font-semibold tabular-nums text-ink-base shadow-[0_0_0_2px_var(--surface-base)]"
			>
				<i class="lucide-check size-3.5" aria-hidden="true" />
				{{ line.qty }} in cart
			</span>
		</div>

		<div class="flex flex-1 flex-col gap-1 p-3">
			<h3 class="line-clamp-2 text-base font-medium leading-snug text-ink-gray-9">
				{{ item.item_name }}
			</h3>
			<p class="text-p-sm tabular-nums">
				<span class="font-semibold text-ink-gray-9">{{ money(item.rate, currency) }}</span>
				<span class="text-ink-gray-6"> / {{ item.uom }}</span>
			</p>

			<div class="mt-auto pt-2">
				<QtyStepper
					v-if="line"
					:model-value="line.qty"
					:label="item.item_name"
					@update:model-value="draft.setQty(line, $event)"
				/>
				<Button
					v-else
					class="w-full"
					size="md"
					variant="subtle"
					icon-left="lucide-plus"
					:aria-label="`Add ${item.item_name}`"
					@click="draft.add(item)"
				>
					Add
				</Button>
			</div>
		</div>
	</article>

	<article
		v-else
		class="relative flex min-w-0 items-center gap-3 py-2.5 pl-3.5 pr-2 transition-colors"
		:class="line ? 'bg-surface-gray-1' : 'hover:bg-surface-gray-1'"
	>
		<span
			v-if="line"
			class="absolute inset-y-0 left-0 w-[3px] bg-surface-gray-10"
			aria-hidden="true"
		/>
		<div
			class="grid size-11 shrink-0 place-items-center overflow-hidden rounded-6 bg-surface-gray-2"
		>
			<img
				v-if="item.image"
				:src="item.image"
				:alt="item.item_name"
				loading="lazy"
				class="size-full object-cover"
			/>
			<span v-else class="text-sm font-semibold text-ink-gray-5" aria-hidden="true">
				{{ initials }}
			</span>
		</div>

		<div class="min-w-0 flex-1">
			<h3 class="truncate text-base font-medium text-ink-gray-9">{{ item.item_name }}</h3>
			<p class="truncate text-p-sm tabular-nums">
				<span class="font-semibold text-ink-gray-9">{{ money(item.rate, currency) }}</span>
				<span class="text-ink-gray-6"> / {{ item.uom }}</span>
				<span v-if="item.item_group" class="hidden text-ink-gray-5 sm:inline">
					· {{ item.item_group }}
				</span>
			</p>
		</div>

		<QtyStepper
			v-if="line"
			class="w-32 shrink-0"
			size="sm"
			:model-value="line.qty"
			:label="item.item_name"
			@update:model-value="draft.setQty(line, $event)"
		/>
		<Button
			v-else
			class="w-32 shrink-0"
			variant="subtle"
			icon-left="lucide-plus"
			:aria-label="`Add ${item.item_name}`"
			@click="draft.add(item)"
		>
			Add
		</Button>
	</article>
</template>
