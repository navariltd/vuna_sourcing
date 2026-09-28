<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { Button, FrappeUIProvider, Spinner } from "frappe-ui";
import PortalShell from "@/components/PortalShell.vue";
import { usePortalStore } from "@/stores/portal";
import { session } from "@/data/session";

const portal = usePortalStore();
const route = useRoute();

const isPublic = computed(() => !!route.meta.public);

const errorMessage = computed(() => {
	const error = portal.session.error as { messages?: string[]; message?: string } | null;
	if (!error) return null;
	return "You do not have access to this portal.";
});
</script>

<template>
	<FrappeUIProvider>
		<RouterView v-if="isPublic" />

		<PortalShell v-else-if="portal.session.data" />

		<div
			v-else-if="errorMessage"
			class="flex h-full flex-col items-center justify-center gap-3 px-6 text-center"
		>
			<div class="flex size-11 items-center justify-center rounded-full bg-surface-gray-2">
				<i class="lucide-lock size-5 text-ink-gray-6" />
			</div>
			<h1 class="text-lg font-semibold text-ink-gray-9">Portal access needed</h1>
			<p class="max-w-md text-p-base text-ink-gray-6">{{ errorMessage }}</p>
			<p class="max-w-md text-p-sm text-ink-gray-5">
				Portal access is granted by adding you to a supplier or customer record and giving
				you the matching role. Ask your contact to set that up.
			</p>
			<Button label="Sign out" icon-left="lucide-log-out" @click="session.logout.submit()" />
		</div>

		<div v-else class="flex h-full items-center justify-center">
			<Spinner class="size-5" />
		</div>
	</FrappeUIProvider>
</template>
