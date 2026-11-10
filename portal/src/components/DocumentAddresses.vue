<script setup lang="ts">
import { computed } from "vue";
import RichText from "@/components/RichText.vue";
import type { DocumentAddresses } from "@/data/selling";

const props = defineProps<{ addresses: DocumentAddresses | null | undefined }>();

function plain(html: string | null | undefined) {
	return (html ?? "")
		.replace(/<[^>]*>/g, " ")
		.replace(/\s+/g, " ")
		.trim();
}

const cards = computed(() => {
	const billing = props.addresses?.billing || null;
	const shipping = props.addresses?.shipping || null;

	if (billing && shipping && plain(billing) === plain(shipping)) {
		return [
			{ key: "both", label: "Billing and delivery", icon: "lucide-map-pin", html: billing },
		];
	}

	return [
		billing && { key: "billing", label: "Bill to", icon: "lucide-receipt", html: billing },
		shipping && { key: "shipping", label: "Ship to", icon: "lucide-truck", html: shipping },
	].filter((card): card is { key: string; label: string; icon: string; html: string } => !!card);
});
</script>

<template>
	<aside
		v-if="cards.length"
		class="grid gap-4 sm:grid-cols-2 lg:sticky lg:top-6 lg:grid-cols-1"
		aria-label="Addresses"
	>
		<section v-for="card in cards" :key="card.key" class="rounded-6 border p-4">
			<h2 class="flex items-center gap-1.5 text-xs uppercase tracking-wide text-ink-gray-5">
				<i :class="card.icon" class="size-3.5" aria-hidden="true" />
				{{ card.label }}
			</h2>
			<RichText class="mt-2 break-words" :html="card.html" />
		</section>
	</aside>
</template>
