<script setup lang="ts">
import { Breadcrumbs } from "frappe-ui";
import type { RouteLocationRaw } from "vue-router";

defineProps<{
	title: string;
	subtitle?: string;
	breadcrumbs?: { label: string; route?: RouteLocationRaw }[];
	wide?: boolean;
}>();
</script>

<template>
	<div
		class="mx-auto w-full px-4 py-6 sm:px-6 sm:py-8"
		:class="wide ? 'max-w-7xl' : 'max-w-4xl'"
	>
		<Breadcrumbs v-if="breadcrumbs?.length" :items="breadcrumbs" class="mb-4" />

		<header class="mb-6 flex flex-wrap items-start justify-between gap-3">
			<div class="min-w-0">
				<h1 class="text-xl font-semibold text-ink-gray-9">{{ title }}</h1>
				<p v-if="subtitle" class="mt-1 text-p-base text-ink-gray-6">{{ subtitle }}</p>
			</div>
			<div class="flex shrink-0 items-center gap-2">
				<slot name="actions" />
			</div>
		</header>

		<slot />
	</div>
</template>
