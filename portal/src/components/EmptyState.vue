<script setup lang="ts">
withDefaults(
	defineProps<{
		title: string;
		description?: string;
		icon?: string;
		dashed?: boolean;
	}>(),
	{ icon: "lucide-inbox", dashed: true }
);
</script>

<template>
	<div
		class="flex flex-col items-center justify-center px-6 py-16 text-center"
		:class="dashed ? 'rounded-6 border border-dashed' : ''"
	>
		<div class="mb-3 flex size-10 items-center justify-center rounded-full bg-surface-gray-2">
			<i :class="[icon, 'size-5 text-ink-gray-5']" aria-hidden="true" />
		</div>

		<p class="text-base font-medium text-ink-gray-7">{{ title }}</p>
		<p v-if="description" class="mx-auto mt-1 max-w-md text-p-sm text-ink-gray-5">
			{{ description }}
		</p>

		<div v-if="$slots.default" class="mt-4 flex flex-wrap items-center justify-center gap-2">
			<slot />
		</div>
	</div>
</template>
