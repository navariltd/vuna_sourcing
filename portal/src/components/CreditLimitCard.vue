<script setup lang="ts">
import { computed } from "vue";
import { SidebarCard } from "frappe-ui";
import { useCreditStatus } from "@/composables/useCreditStatus";
import { usePortalSettings } from "@/composables/usePortalSettings";
import { money } from "@/data/purchase";

const credit = useCreditStatus();
const settings = usePortalSettings();

const card = computed(() => {
	const over = credit.overRows.value;
	if (over.length === 1) {
		const row = over[0]!;
		return {
			theme: "red" as const,
			title: "Credit limit reached",
			description: `You are ${money(row.over_by, row.currency)} over your limit with ${
				row.company
			}.`,
		};
	}
	if (over.length > 1) {
		return {
			theme: "red" as const,
			title: "Credit limit reached",
			description: `You are over your limit with ${over.length} companies: ${over
				.map((row) => `${row.company} by ${money(row.over_by, row.currency)}`)
				.join(", ")}.`,
		};
	}
	const near = credit.nearRows.value;
	if (near.length) {
		const row = near[0]!;
		return {
			theme: "amber" as const,
			title: "Close to your credit limit",
			description: `${money(row.available, row.currency)} left with ${row.company}${
				near.length > 1 ? ` and ${near.length - 1} more` : ""
			}.`,
		};
	}
	return null;
});
</script>

<template>
	<SidebarCard
		v-if="card"
		:theme="card.theme"
		:title="card.title"
		:description="card.description"
		:action="{ label: 'View my credit', onClick: () => settings.show('credit') }"
	/>
</template>
