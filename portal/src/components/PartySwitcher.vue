<script setup lang="ts">
import { computed } from "vue";
import { Avatar, Dropdown } from "frappe-ui";
import { partyKey, usePortalStore } from "@/stores/portal";
import { PARTY_COPY } from "@/data/parties";
import { usePartySwitch } from "@/composables/usePartySwitch";

const portal = usePortalStore();
const { setActiveParty, switchToType } = usePartySwitch();

const sides = computed(() => portal.partyTypesJoined);
const siblings = computed(() => portal.activeSiblings);
const activeType = computed(() => portal.activeParty?.party_type ?? null);

const show = computed(() => portal.isMultiParty);
const showSides = computed(() => sides.value.length > 1);
const showAccounts = computed(() => siblings.value.length > 1);

const accountOptions = computed(() =>
	siblings.value.map((party) => ({
		label: party.title,
		selected: partyKey(party) === portal.activePartyKey,
		onClick: () => setActiveParty(party),
	}))
);
</script>

<template>
	<div v-if="show">
		<div
			v-if="showSides"
			role="group"
			aria-label="Act as supplier or customer"
			class="flex gap-0.5 rounded-5 bg-surface-gray-2 p-0.5"
		>
			<button
				v-for="side in sides"
				:key="side"
				type="button"
				:aria-pressed="side === activeType"
				class="flex flex-1 items-center justify-center gap-1.5 rounded-4 px-2 py-1 text-base font-medium transition-colors"
				:class="
					side === activeType
						? 'bg-surface-white text-ink-gray-8 shadow-sm'
						: 'text-ink-gray-6 hover:text-ink-gray-8'
				"
				@click="switchToType(side)"
			>
				<i :class="[PARTY_COPY[side].icon, 'size-4 shrink-0']" />
				{{ side }}
			</button>
		</div>

		<template v-if="showAccounts">
			<p
				v-if="!showSides"
				class="px-1 pb-0.5 pt-1 text-xs uppercase tracking-wide text-ink-gray-5"
			>
				{{ activeType }} accounts
			</p>

			<Dropdown :options="accountOptions" match-trigger-width class="w-full">
				<button
					type="button"
					class="mt-1 flex w-full items-center gap-2 rounded-4 p-1 text-left hover:bg-surface-gray-2"
				>
					<Avatar
						:image="portal.activeParty?.image || undefined"
						:label="portal.activeParty?.title || '?'"
						size="sm"
						shape="square"
					/>
					<span class="min-w-0 flex-1 truncate text-base text-ink-gray-8">
						{{ portal.activeParty?.title }}
					</span>
					<i class="lucide-chevrons-up-down size-4 shrink-0 text-ink-gray-5" />
				</button>
			</Dropdown>
		</template>
	</div>
</template>
