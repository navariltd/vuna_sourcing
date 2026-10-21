<script setup lang="ts">
import { ref, watch } from "vue";

const props = defineProps<{
	modelValue: number;
	label: string;
	size?: "sm" | "md";
}>();

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
	if (value !== props.modelValue) emit("update:modelValue", value);
}

function step(delta: number) {
	emit("update:modelValue", Math.max(props.modelValue + delta, 0));
}
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
			class="grid h-full shrink-0 place-items-center rounded-l-full text-ink-gray-7 transition-colors hover:bg-surface-gray-2 active:bg-surface-gray-3"
			:class="size === 'sm' ? 'w-8' : 'w-10'"
			:aria-label="modelValue <= 1 ? `Remove ${label}` : `One less ${label}`"
			@click="step(-1)"
		>
			<i
				:class="modelValue <= 1 ? 'lucide-trash-2' : 'lucide-minus'"
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
			class="grid h-full shrink-0 place-items-center rounded-r-full text-ink-gray-7 transition-colors hover:bg-surface-gray-2 active:bg-surface-gray-3"
			:class="size === 'sm' ? 'w-8' : 'w-10'"
			:aria-label="`One more ${label}`"
			@click="step(1)"
		>
			<i class="lucide-plus size-4" aria-hidden="true" />
		</button>
	</div>
</template>
