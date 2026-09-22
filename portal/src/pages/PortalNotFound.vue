<script setup lang="ts">
import { Button } from "frappe-ui";
</script>

<template>
	<div class="flex h-full min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
		<h1 class="text-lg font-semibold text-ink-gray-9">Page not found</h1>
		<p class="text-p-base text-ink-gray-6">
			That page does not exist, or you no longer have access to it.
		</p>
		<Button variant="solid" label="Go to the portal" :route="{ name: 'Home' }" />
	</div>
</template>
