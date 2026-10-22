<script setup lang="ts">
import { computed, ref, watch } from "vue";

const props = withDefaults(
	defineProps<{
		modelValue: number;
		label: string;
		size?: "sm" | "md";
		max?: number;
		removable?: boolean;
	}>(),
	{ max: Infinity, removable: true }
);

const emit = defineEmits<{ (e: "update:modelValue", value: number): void }>();

const text = ref(String(props.modelValue));

watch(
	() => props.modelValue,
	(value) => {
		if (Number(text.value) !== value) text.value = String(value);
	}
);

function commit() {
	const value = Number(text.value);
	if (text.value.trim() === "" || !Number.isFinite(value) || value < 0) {
		text.value = String(props.modelValue);
		return;
	}
	const allowed = Math.min(value, props.max);
	text.value = String(allowed);
	if (allowed !== props.modelValue) emit("update:modelValue", allowed);
}

function step(delta: number) {
	emit("update:modelValue", Math.min(Math.max(props.modelValue + delta, 0), props.max));
}

const showsRemove = computed(() => props.removable && props.modelValue <= 1);
</script>

<template>
	<div
		class="flex items-center rounded-full border border-outline-gray-3 bg-surface-base"
		:class="size === 'sm' ? 'h-8' : 'h-10'"
		role="group"
		:aria-label="`Quantity of ${label}`"
	>
		<button
			type="button"
			class="grid h-full shrink-0 place-items-center rounded-l-full text-ink-gray-7 transition-colors hover:bg-surface-gray-2 active:bg-surface-gray-3 disabled:pointer-events-none disabled:text-ink-gray-3"
			:class="size === 'sm' ? 'w-8' : 'w-10'"
			:disabled="!removable && modelValue <= 0"
			:aria-label="showsRemove ? `Remove ${label}` : `One less ${label}`"
			@click="step(-1)"
		>
			<i
				:class="showsRemove ? 'lucide-trash-2' : 'lucide-minus'"
				class="size-4"
				aria-hidden="true"
			/>
		</button>
		<input
			v-model="text"
			type="text"
			inputmode="decimal"
			class="h-full min-w-0 flex-1 border-0 bg-transparent p-0 text-center text-base font-medium tabular-nums text-ink-gray-9 focus:ring-0"
			:aria-label="`Quantity of ${label}`"
			@blur="commit"
			@keydown.enter="($event.target as HTMLInputElement).blur()"
		/>
		<button
			type="button"
			class="grid h-full shrink-0 place-items-center rounded-r-full text-ink-gray-7 transition-colors hover:bg-surface-gray-2 active:bg-surface-gray-3 disabled:pointer-events-none disabled:text-ink-gray-3"
			:class="size === 'sm' ? 'w-8' : 'w-10'"
			:disabled="modelValue >= max"
			:aria-label="`One more ${label}`"
			@click="step(1)"
		>
			<i class="lucide-plus size-4" aria-hidden="true" />
		</button>
	</div>
</template>
