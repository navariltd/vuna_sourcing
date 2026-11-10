<script setup lang="ts">
import { computed } from "vue";
import { Alert } from "frappe-ui";
import { injectOrderDraft } from "@/composables/useOrderDraft";
import { useCreditStatus } from "@/composables/useCreditStatus";
import { usePortalSettings } from "@/composables/usePortalSettings";
import { orderCreditImpact } from "@/data/credit";
import { money } from "@/data/purchase";

const draft = injectOrderDraft();
const credit = useCreditStatus();
const settings = usePortalSettings();

const row = computed(() => credit.forCompany(draft.company.value));

const orderTotal = computed(() =>
	draft.lines.value.length ? draft.priced.value?.base_grand_total ?? 0 : 0
);

const impact = computed(() => orderCreditImpact(row.value, orderTotal.value));

const alert = computed(() => {
	const current = row.value;
	if (!current || !impact.value) return null;
	const limit = money(current.credit_limit, current.currency);

	if (impact.value.alreadyOver) {
		return {
			theme: "red" as const,
			title: "Your account is over its credit limit",
			description: `You are ${money(
				current.over_by,
				current.currency
			)} over your ${limit} limit with ${
				current.company
			}. You can still send this order. Our team may hold it until a payment comes in.`,
		};
	}

	if (impact.value.overAfter > 0) {
		return {
			theme: "amber" as const,
			title: "This order takes you over your credit limit",
			description: `With this order you would be ${money(
				impact.value.overAfter,
				current.currency
			)} over your ${limit} limit with ${
				current.company
			}. You can still send it. Our team reviews orders above the limit before confirming them.`,
		};
	}

	return null;
});
</script>

<template>
	<Alert
		v-if="alert"
		:theme="alert.theme"
		:title="alert.title"
		:description="alert.description"
		:primary-action="{
			label: 'See my credit',
			variant: 'solid',
			onClick: () => settings.show('credit'),
		}"
	/>
</template>
