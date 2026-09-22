<script setup lang="ts">
import { FormControl } from "frappe-ui";
import type { ApplicationContact } from "@/data/application";

const contact = defineModel<ApplicationContact>({ required: true });

defineProps<{
	full?: boolean;
	disabled?: boolean;
}>();
</script>

<template>
	<div class="grid gap-4 sm:grid-cols-2">
		<FormControl
			v-model="contact.first_name"
			label="First name"
			required
			:disabled="disabled"
		/>
		<FormControl
			v-model="contact.last_name"
			label="Last name"
			:required="full"
			:disabled="disabled"
		/>
		<FormControl
			v-model="contact.email_id"
			type="email"
			label="Email address"
			required
			:disabled="disabled"
		/>
		<FormControl
			v-model="contact.mobile_no"
			label="Mobile number"
			:required="full"
			:disabled="disabled"
		/>
		<FormControl
			v-if="full"
			v-model="contact.designation"
			label="Designation"
			:disabled="disabled"
		/>
	</div>
</template>
