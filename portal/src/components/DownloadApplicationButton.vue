<script setup lang="ts">
import { ref } from "vue";
import { Button, toast } from "frappe-ui";
import { downloadApplication } from "@/data/application";

const props = defineProps<{ name: string; beforeDownload?: () => Promise<unknown> }>();

const downloading = ref(false);

async function download() {
	if (downloading.value) return;
	downloading.value = true;
	try {
		await props.beforeDownload?.();
		await downloadApplication(props.name);
	} catch (error: any) {
		toast.error(
			error?.messages?.[0] || error?.message || "We could not prepare the download."
		);
	} finally {
		downloading.value = false;
	}
}
</script>

<template>
	<Button
		variant="outline"
		icon-left="lucide-download"
		label="Download PDF"
		:loading="downloading"
		@click="download"
	/>
</template>
