<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Combobox, FormLabel, createResource } from "frappe-ui";

const props = defineProps<{
	modelValue: string | null | undefined;
	doctype: "Country";
	label: string;
	placeholder?: string;
	required?: boolean;
	description?: string;
}>();

const emit = defineEmits<{ (e: "update:modelValue", value: string | null): void }>();

const options = createResource({
	url: "vuna_sourcing.api.onboarding.get_link_options",
	auto: false,
});

const query = ref("");

function load(search = "") {
	options.fetch({ doctype: props.doctype, search: search || null });
}

onMounted(() => load());
watch(query, (value) => load(value));

const items = computed(() => (options.data as { label: string; value: string }[]) ?? []);

const selected = computed({
	get: () => props.modelValue ?? null,
	set: (value: any) => emit("update:modelValue", value?.value ?? value ?? null),
});
</script>

<template>
	<div>
		<FormLabel :label="label" :required="required" />
		<Combobox
			v-model="selected"
			class="mt-1"
			:options="items"
			:placeholder="placeholder || `Select ${label.toLowerCase()}`"
			@update:query="query = $event"
		/>
		<p v-if="description" class="mt-1.5 text-p-sm text-ink-gray-5">{{ description }}</p>
	</div>
</template>
