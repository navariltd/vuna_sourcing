<script setup lang="ts">
import { computed } from "vue";
import { FormControl, Radio, RadioGroup } from "frappe-ui";
import type { DynamicFieldDefinition, DynamicFieldValue } from "@/data/dynamicFields";
import { RADIO_LIMIT, TEXT_LIMITS } from "@/data/dynamicFields";

const props = defineProps<{
	field: DynamicFieldDefinition;
	error?: string;
	disabled?: boolean;
}>();

const model = defineModel<DynamicFieldValue>({ default: null });

const isText = computed(
	() => props.field.field_type === "Short Text" || props.field.field_type === "Long Text"
);
const isNumber = computed(
	() => props.field.field_type === "Whole Number" || props.field.field_type === "Number"
);
const isChoice = computed(
	() => props.field.field_type === "Yes / No" || props.field.field_type === "Multiple Choice"
);
const asRadios = computed(() => props.field.choices.length <= RADIO_LIMIT);

const textValue = computed({
	get: () => (model.value === null || model.value === undefined ? "" : String(model.value)),
	set: (value: string) => {
		model.value = value === "" ? null : value;
	},
});

const choiceValue = computed({
	get: () => (typeof model.value === "string" ? model.value : undefined),
	set: (value: string | number | boolean | undefined) => {
		model.value = value === undefined || value === "" ? null : String(value);
	},
});

const selectOptions = computed(() => [
	{ label: "Choose…", value: "" },
	...props.field.choices.map((choice) => ({ label: choice, value: choice })),
]);
</script>

<template>
	<FormControl
		v-if="isText"
		v-model="textValue"
		:type="field.field_type === 'Long Text' ? 'textarea' : 'text'"
		:label="field.label"
		:description="field.description ?? undefined"
		:required="field.mandatory"
		:error="error"
		:disabled="disabled"
		:maxlength="TEXT_LIMITS[field.field_type]"
	/>
	<FormControl
		v-else-if="isNumber"
		v-model="textValue"
		type="number"
		inputmode="decimal"
		:step="field.field_type === 'Whole Number' ? 1 : 'any'"
		:label="field.label"
		:description="field.description ?? undefined"
		:required="field.mandatory"
		:error="error"
		:disabled="disabled"
	/>
	<FormControl
		v-else-if="field.field_type === 'Date'"
		v-model="textValue"
		type="date"
		:label="field.label"
		:description="field.description ?? undefined"
		:required="field.mandatory"
		:error="error"
		:disabled="disabled"
	/>
	<RadioGroup
		v-else-if="isChoice && asRadios"
		v-model="choiceValue"
		:label="field.label"
		:description="field.description ?? undefined"
		:required="field.mandatory"
		:error="error"
		:disabled="disabled"
		:orientation="field.field_type === 'Yes / No' ? 'horizontal' : 'vertical'"
	>
		<Radio v-for="choice in field.choices" :key="choice" :value="choice" :label="choice" />
	</RadioGroup>
	<FormControl
		v-else
		v-model="textValue"
		type="select"
		:options="selectOptions"
		:label="field.label"
		:description="field.description ?? undefined"
		:required="field.mandatory"
		:error="error"
		:disabled="disabled"
	/>
</template>
