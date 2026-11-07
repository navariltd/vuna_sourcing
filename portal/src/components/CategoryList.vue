<script setup lang="ts">
import { Button, ErrorMessage, Spinner, TextInput } from "frappe-ui";
import type { OrderCategories } from "@/composables/useOrderCategories";

const props = defineProps<{ categories: OrderCategories; selected: string | null }>();
const emit = defineEmits<{ (e: "select", name: string | null): void }>();

const { rows, hasMore, allItems, query, loading, error } = props.categories;
</script>

<template>
	<div class="flex min-h-0 flex-col gap-2">
		<TextInput
			v-model="query"
			type="search"
			size="md"
			placeholder="Find a category"
			aria-label="Find a category"
		>
			<template #prefix>
				<i class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
			</template>
		</TextInput>

		<ErrorMessage v-if="error" :message="error" />

		<ul class="flex flex-col gap-0.5" aria-label="Item categories">
			<li v-if="!query.trim()">
				<button
					type="button"
					class="category-row"
					:class="selected === null ? 'is-active' : ''"
					:aria-pressed="selected === null"
					@click="emit('select', null)"
				>
					<span class="flex min-w-0 items-center gap-2">
						<i class="lucide-layout-grid size-4 shrink-0" aria-hidden="true" />
						<span class="truncate">All items</span>
					</span>
					<span v-if="allItems != null" class="category-count">{{ allItems }}</span>
				</button>
			</li>
			<li v-for="row in rows" :key="row.name">
				<button
					type="button"
					class="category-row"
					:class="selected === row.name ? 'is-active' : ''"
					:aria-pressed="selected === row.name"
					:title="row.name"
					@click="emit('select', row.name)"
				>
					<span class="truncate">{{ row.name }}</span>
					<span class="category-count">{{ row.count }}</span>
				</button>
			</li>
		</ul>

		<p
			v-if="!loading && !rows.length && query.trim()"
			class="px-2 py-3 text-p-sm text-ink-gray-5"
		>
			No category matches “{{ query.trim() }}”.
		</p>

		<div v-if="loading" class="flex justify-center py-2">
			<Spinner class="size-4" />
		</div>
		<Button
			v-else-if="hasMore"
			variant="ghost"
			icon-left="lucide-chevron-down"
			label="Show more categories"
			@click="categories.loadMore()"
		/>
	</div>
</template>

<style scoped>
.category-row {
	display: flex;
	width: 100%;
	min-height: 2.25rem;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	border-radius: 0.375rem;
	padding: 0.375rem 0.5rem;
	text-align: left;
	font-size: 0.875rem;
	color: var(--ink-gray-7);
	transition: background-color 120ms;
}

.category-row:hover {
	background-color: var(--surface-gray-2);
}

.category-row:focus-visible {
	outline: var(--focus-outline-default);
	outline-offset: 1px;
}

.category-row.is-active {
	background-color: var(--surface-gray-10);
	color: var(--ink-base);
	font-weight: 500;
}

.category-count {
	flex-shrink: 0;
	font-size: 0.75rem;
	font-variant-numeric: tabular-nums;
	color: var(--ink-gray-5);
}

.category-row.is-active .category-count {
	color: var(--ink-base);
}
</style>
