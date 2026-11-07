<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { Button, Dropdown, FormControl, TextInput, debounce } from "frappe-ui";

export interface FilterOption {
	label: string;
	value: string;
	count?: number;
}

export interface FilterField {
	field: string;
	label: string;
	type: "select" | "text" | "date";
	options?: FilterOption[];
	placeholder?: string;
}

const props = defineProps<{
	fields: FilterField[];
	modelValue: Record<string, string>;
	searchPlaceholder?: string;
}>();

const emit = defineEmits<{
	"update:modelValue": [value: Record<string, string>];
}>();

const applied = computed(() =>
	props.fields.filter((field) => {
		const value = props.modelValue[field.field];
		return value !== undefined && value !== null && value !== "";
	})
);

const unapplied = computed(() => props.fields.filter((field) => !applied.value.includes(field)));

const addOptions = computed(() =>
	unapplied.value.map((field) => ({
		label: field.label,
		onClick: () =>
			set(field.field, field.type === "select" ? field.options?.[0]?.value ?? "" : ""),
	}))
);

const SEARCH_DELAY_MS = 300;

const searchText = ref(props.modelValue.search ?? "");

watch(
	() => props.modelValue.search ?? "",
	(search) => {
		if (search !== searchText.value) searchText.value = search;
	}
);

const emitSearch = debounce((search: string) => set("search", search), SEARCH_DELAY_MS);

function onSearchInput(value: unknown) {
	searchText.value = String(value ?? "");
	emitSearch(searchText.value);
}

onBeforeUnmount(() => emitSearch.cancel());

function set(field: string, value: string) {
	emit("update:modelValue", { ...props.modelValue, [field]: value });
}

function remove(field: string) {
	const next = { ...props.modelValue };
	delete next[field];
	emit("update:modelValue", next);
}

function clearAll() {
	emit("update:modelValue", {});
}

function optionsFor(field: FilterField) {
	return (field.options ?? []).map((option) => ({
		label: option.count === undefined ? option.label : `${option.label} (${option.count})`,
		value: option.value,
	}));
}
</script>

<template>
	<div class="flex flex-wrap items-center gap-2">
		<TextInput
			class="w-full sm:w-64"
			type="text"
			size="sm"
			:placeholder="searchPlaceholder || 'Search'"
			:model-value="searchText"
			@update:model-value="onSearchInput"
		>
			<template #prefix>
				<i class="lucide-search size-4 text-ink-gray-5" />
			</template>
		</TextInput>

		<div class="flex flex-wrap items-center gap-2 sm:ms-auto">
			<div
				v-for="field in applied"
				:key="field.field"
				class="flex items-center gap-1 rounded-4 border border-outline-gray-2 bg-surface-base px-1.5 py-0.5"
			>
				<span class="text-xs text-ink-gray-5">{{ field.label }}</span>

				<FormControl
					v-if="field.type === 'select'"
					type="select"
					size="sm"
					:options="optionsFor(field)"
					:model-value="modelValue[field.field]"
					@update:model-value="set(field.field, String($event ?? ''))"
				/>
				<FormControl
					v-else
					:type="field.type === 'date' ? 'date' : 'text'"
					size="sm"
					:placeholder="field.placeholder"
					:model-value="modelValue[field.field]"
					@update:model-value="set(field.field, String($event ?? ''))"
				/>

				<button
					type="button"
					class="rounded-4 p-0.5 text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-7"
					:aria-label="`Remove ${field.label} filter`"
					@click="remove(field.field)"
				>
					<i class="lucide-x size-3.5" />
				</button>
			</div>

			<Button
				v-if="applied.length > 1"
				variant="ghost"
				label="Clear all"
				@click="clearAll"
			/>

			<Dropdown v-if="addOptions.length" :options="addOptions" placement="bottom-end">
				<Button variant="subtle" icon-left="lucide-list-filter" label="Filter" />
			</Dropdown>
		</div>
	</div>
</template>
