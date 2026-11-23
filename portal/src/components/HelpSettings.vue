<script setup lang="ts">
import { Button } from "frappe-ui";
import { usePortalStore } from "@/stores/portal";

const portal = usePortalStore();
</script>

<template>
	<div class="flex flex-col items-start gap-3">
		<p class="max-w-md text-p-sm text-ink-gray-6">
			Stuck on something, or found a problem? Raise a ticket and our support team will get
			back to you. You can follow its progress on the help desk.
		</p>
		<Button
			v-if="portal.helpUrl"
			variant="solid"
			label="Raise a ticket"
			icon-left="lucide-life-buoy"
			icon-right="lucide-external-link"
			:href="portal.helpUrl"
		/>
	</div>
</template>
