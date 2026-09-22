<script setup lang="ts">
import { computed, watch } from "vue";
import { Badge, Button, Spinner, createResource } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import { usePortalStore } from "@/stores/portal";

const portal = usePortalStore();

const party = createResource({
	url: "vuna_sourcing.api.portal.get_party",
	auto: false,
});

function load() {
	const active = portal.activeParty;
	if (!active) return;
	party.fetch({ party_type: active.party_type, party: active.name });
}

watch(() => portal.activePartyKey, load, { immediate: true });

const details = computed(() => {
	const d = party.data;
	if (!d) return [];
	return [
		["Type", d.entity_type || d.party_type],
		[`${d.party_type} group`, d.group],
		...(d.party_type === "Customer" ? [["Territory", d.territory]] : []),
		["Country", d.country],
		["Billing currency", d.default_currency],
		["Tax registration", d.tax_id],
		["Website", d.website],
	];
});
</script>

<template>
	<PageContainer
		:title="portal.activeParty?.title || 'Overview'"
		:subtitle="
			portal.isMultiParty
				? 'Switch between the businesses you act for using the rail on the left.'
				: undefined
		"
	>
		<template #actions>
			<Badge
				v-if="portal.activeParty"
				theme="gray"
				variant="subtle"
				:label="portal.activeParty.party_type"
			/>
		</template>

		<div v-if="party.loading && !party.data" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<div v-else-if="party.data" class="space-y-6">
			<dl class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-2">
				<div v-for="row in details" :key="row[0] as string">
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">{{ row[0] }}</dt>
					<dd class="text-p-base text-ink-gray-8">{{ row[1] || "—" }}</dd>
				</div>
			</dl>

			<div class="rounded-6 border border-dashed p-6 text-center">
				<p class="text-base font-medium text-ink-gray-7">More is on the way</p>
				<p class="mx-auto mt-1 max-w-md text-p-sm text-ink-gray-5">
					{{
						portal.activeParty?.party_type === "Customer"
							? "Orders, invoices and deliveries will appear here."
							: "Purchase orders, invoices and payment status will appear here."
					}}
					For now you can track your onboarding.
				</p>
				<Button
					class="mt-4"
					variant="subtle"
					label="My applications"
					:route="{ name: 'ApplicationList' }"
				/>
			</div>
		</div>
	</PageContainer>
</template>
