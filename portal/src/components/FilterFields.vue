<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { Button, FormControl, TextInput, debounce } from "frappe-ui";

export interface StatusOption {
	label: string;
	value: string;
	count?: number;
}

const props = defineProps<{
	modelValue: Record<string, string>;
	statuses: StatusOption[];
	dates?: boolean;
	searchPlaceholder?: string;
}>();

const emit = defineEmits<{ "update:modelValue": [value: Record<string, string>] }>();

const SEARCH_DELAY_MS = 300;

const searchText = ref(props.modelValue.search ?? "");

watch(
	() => props.modelValue.search ?? "",
	(search) => {
		if (search !== searchText.value) searchText.value = search;
	}
);

const emitSearch = debounce((search: string) => set("search", search), SEARCH_DELAY_MS);

onBeforeUnmount(() => emitSearch.cancel());

function onSearchInput(value: unknown) {
	searchText.value = String(value ?? "");
	emitSearch(searchText.value);
}

function set(field: string, value: string) {
	const next = { ...props.modelValue, [field]: value };
	if (!value) delete next[field];
	emit("update:modelValue", next);
}

const statusOptions = computed(() =>
	props.statuses.map((option) => ({
		label: option.count === undefined ? option.label : `${option.label} (${option.count})`,
		value: option.value,
	}))
);

const anySet = computed(() => Object.values(props.modelValue).some(Boolean));

function clearAll() {
	emitSearch.cancel();
	searchText.value = "";
	emit("update:modelValue", {});
}
</script>

<template>
	<div class="grid grid-cols-2 items-end gap-2 sm:flex sm:flex-wrap">
		<TextInput
			class="col-span-2 sm:w-64"
			type="text"
			size="md"
			:placeholder="searchPlaceholder || 'Search'"
			:model-value="searchText"
			aria-label="Search"
			@update:model-value="onSearchInput"
		>
			<template #prefix>
				<i class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
			</template>
		</TextInput>

		<FormControl
			class="col-span-2 sm:w-48"
			type="select"
			size="md"
			aria-label="Status"
			placeholder="Status"
			:options="statusOptions"
			:model-value="modelValue.status ?? ''"
			@update:model-value="set('status', String($event ?? ''))"
		/>

		<template v-if="dates">
			<FormControl
				class="sm:w-40"
				type="date"
				size="md"
				placeholder="From date"
				aria-label="From date"
				:model-value="modelValue.from_date ?? ''"
				@update:model-value="set('from_date', String($event ?? ''))"
			/>
			<FormControl
				class="sm:w-40"
				type="date"
				size="md"
				placeholder="To date"
				aria-label="To date"
				:model-value="modelValue.to_date ?? ''"
				@update:model-value="set('to_date', String($event ?? ''))"
			/>
		</template>

		<Button
			v-if="anySet"
			class="col-span-2 sm:col-span-1"
			variant="subtle"
			size="md"
			icon-left="lucide-x"
			label="Clear filters"
			@click="clearAll"
		/>
	</div>
</template>
