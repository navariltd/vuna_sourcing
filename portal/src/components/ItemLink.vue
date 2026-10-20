<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { Combobox } from "frappe-ui";
import { fetchOrderableItems } from "@/data/orders";
import type { OrderableItem } from "@/data/orders";
import { money } from "@/data/purchase";
import { isOk } from "@/types/api";

const props = defineProps<{
	modelValue: string | null;
	label?: string | null;
	customer: string;
	company: string | null;
	ariaLabel?: string;
}>();

const emit = defineEmits<{ (e: "select", item: OrderableItem): void }>();

const results = ref<OrderableItem[]>([]);
const currency = ref<string | null>(null);
const loading = ref(false);
let request = 0;
let searchTimer: ReturnType<typeof setTimeout> | undefined;

async function search(text: string) {
	if (!props.company) return;

	const mine = ++request;
	loading.value = true;
	try {
		const response = await fetchOrderableItems({
			customer: props.customer,
			company: props.company,
			search: text.trim() || null,
			limit: 20,
		});
		if (mine !== request) return;
		if (isOk(response)) {
			results.value = response.data.rows;
			currency.value = response.data.currency;
		}
	} catch {
		if (mine === request) results.value = [];
	} finally {
		if (mine === request) loading.value = false;
	}
}

function onQuery(text: string) {
	clearTimeout(searchTimer);
	if (text === (props.label ?? "")) return;
	searchTimer = setTimeout(() => search(text), 250);
}

function onOpen(open: boolean) {
	if (open && !results.value.length) search("");
}

onBeforeUnmount(() => clearTimeout(searchTimer));

const options = computed(() => {
	const rows = results.value.map((item) => ({
		label: item.item_name,
		value: item.item_code,
		description: `${item.item_code} · ${
			item.rate ? `${money(item.rate, currency.value)} / ${item.uom}` : "No price yet"
		}`,
	}));
	if (props.modelValue && !rows.some((row) => row.value === props.modelValue)) {
		rows.unshift({
			label: props.label || props.modelValue,
			value: props.modelValue,
			description: "",
		});
	}
	return rows;
});

function onSelect(value: string | number | null | undefined) {
	const item = results.value.find((row) => row.item_code === value);
	if (item) emit("select", item);
}
</script>

<template>
	<Combobox
		:model-value="modelValue"
		:options="options"
		:filterable="false"
		:loading="loading"
		:aria-label="ariaLabel"
		variant="ghost"
		placeholder="Search items"
		empty-text="No item matches that search"
		open-on-focus
		open-on-click
		@update:query="onQuery"
		@update:open="onOpen"
		@update:model-value="onSelect"
	/>
</template>
