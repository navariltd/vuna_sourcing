<script setup lang="ts">
import { FormControl } from "frappe-ui";
import LinkSelect from "@/components/LinkSelect.vue";
import type { ApplicationAddress } from "@/data/application";

const address = defineModel<ApplicationAddress>({ required: true });

defineProps<{
	typeOptions?: string[];
}>();
</script>

<template>
	<div class="grid gap-4 sm:grid-cols-2">
		<FormControl
			v-if="typeOptions?.length"
			v-model="address.address_type"
			type="select"
			label="Kind of address"
			:options="typeOptions"
			class="sm:col-span-2"
		/>
		<FormControl v-model="address.address_line1" label="Address line 1" required />
		<FormControl v-model="address.address_line2" label="Address line 2" />
		<FormControl v-model="address.city" label="City / town" required />
		<FormControl v-model="address.state" label="County / state" />
		<FormControl v-model="address.pincode" label="Postal code" />
		<LinkSelect v-model="address.country" doctype="Country" label="Country" required />
	</div>
</template>
