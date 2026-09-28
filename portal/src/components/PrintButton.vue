<script setup lang="ts">
import { ref } from "vue";
import { Button, toast } from "frappe-ui";

const props = defineProps<{
	doctype: string;
	name: string;
	label: string;
}>();

const printing = ref(false);

function refusalMessage(status: number) {
	if (status === 403) {
		return `Printing this ${props.label} is not switched on for your account yet. Ask your contact on our team to enable it.`;
	}
	if (status === 404) {
		return `We could not find this ${props.label}. It may have been withdrawn.`;
	}
	return `We could not prepare this ${props.label} for printing. Please try again in a moment.`;
}

async function print() {
	if (printing.value) return;
	printing.value = true;

	const tab = window.open("", "_blank");
	const query = new URLSearchParams({ doctype: props.doctype, name: props.name });

	try {
		const response = await fetch(
			`/api/method/frappe.utils.print_format.download_pdf?${query}`,
			{ credentials: "same-origin" }
		);
		if (!response.ok) throw response.status;

		const url = URL.createObjectURL(await response.blob());
		if (tab) tab.location.href = url;
		else window.open(url, "_blank");
		setTimeout(() => URL.revokeObjectURL(url), 60_000);
	} catch (status) {
		tab?.close();
		toast.error(refusalMessage(typeof status === "number" ? status : 0));
	} finally {
		printing.value = false;
	}
}
</script>

<template>
	<Button
		variant="subtle"
		icon-left="lucide-printer"
		label="Print"
		:loading="printing"
		@click="print"
		theme="blue"
	/>
</template>
