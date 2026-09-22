<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import {
	Avatar,
	DesktopShell,
	Dropdown,
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarLabel,
	SidebarRail,
	SidebarRailItem,
} from "frappe-ui";
import { partyKey, usePortalStore } from "@/stores/portal";
import type { Party } from "@/stores/portal";
import { session } from "@/data/session";
import { PARTY_COPY } from "@/data/parties";

const portal = usePortalStore();
const route = useRoute();

const showRail = computed(() => portal.parties.length > 1);

const activeKey = computed(() => (portal.activeParty ? partyKey(portal.activeParty) : null));

const headerTitle = computed(() => portal.activeParty?.title ?? "Sourcing Portal");

const headerSubtitle = computed(() => {
	if (portal.activeParty) return portal.activeParty.party_type;
	return portal.isApplicant ? "Application in progress" : portal.user?.full_name;
});

const userMenu = computed(() => [
	{
		label: "Frappe Desk",
		icon: "lucide-layout-grid",
		onClick: () => {
			window.location.href = "/app";
		},
		condition: () => !portal.user?.is_website_user,
	},
	{
		label: "Sign out",
		icon: "lucide-log-out",
		onClick: () => session.logout.submit(),
	},
]);

function switchParty(party: Party) {
	portal.setActiveParty(party);
}
</script>

<template>
	<DesktopShell>
		<template v-if="showRail" #rail>
			<SidebarRail class="gap-2 !bg-surface-gray-4">
				<SidebarRailItem
					v-for="party in portal.parties"
					:key="partyKey(party)"
					:label="party.title"
					:description="party.party_type"
					:active="partyKey(party) === activeKey"
					@click="switchParty(party)"
				>
					<Avatar
						:image="party.image || undefined"
						:label="party.title"
						size="lg"
						shape="square"
					/>
				</SidebarRailItem>

				<div class="mt-auto flex flex-col items-center gap-2 pb-1">
					<SidebarRailItem
						v-if="portal.canApply"
						label="New application"
						description="Apply as a supplier or customer"
						icon="lucide-plus"
						variant="ghost"
						:route="{ name: 'ApplicationForm' }"
					/>
				</div>
			</SidebarRail>
		</template>

		<template #sidebar>
			<Sidebar>
				<SidebarHeader
					:title="headerTitle"
					:subtitle="headerSubtitle || undefined"
					:show-logo="!showRail"
				>
					<template v-if="!showRail" #prefix>
						<Avatar
							:image="portal.activeParty?.image || undefined"
							:label="headerTitle"
							size="md"
							shape="square"
						/>
					</template>
				</SidebarHeader>

				<div class="flex-1 overflow-y-auto px-2 py-1">
					<SidebarItem
						v-if="portal.hasParties"
						label="Overview"
						icon="lucide-layout-dashboard"
						:route="{ name: 'PortalOverview' }"
					/>

					<SidebarLabel divider>Onboarding</SidebarLabel>

					<SidebarItem
						v-if="portal.canApply && !portal.hasParties"
						label="Application"
						icon="lucide-file-pen-line"
						:route="{ name: 'ApplicationForm' }"
					/>
					<template v-else>
						<SidebarItem
							v-for="partyType in portal.partyTypesToJoin"
							:key="partyType"
							:label="`Become a ${PARTY_COPY[partyType].noun}`"
							:icon="PARTY_COPY[partyType].icon"
							:route="{
								name: 'ApplicationForm',
								query: { as: partyType.toLowerCase() },
							}"
						/>
					</template>
					<SidebarItem
						label="My applications"
						icon="lucide-folder-clock"
						:route="{ name: 'ApplicationList' }"
					/>
				</div>

				<div class="border-t p-2">
					<Dropdown :options="userMenu" placement="top-start" class="w-full">
						<button
							class="flex w-full items-center gap-2 rounded-4 p-1 text-left hover:bg-surface-gray-2"
						>
							<Avatar
								:image="portal.user?.image || undefined"
								:label="portal.user?.full_name || '?'"
								size="md"
							/>
							<span class="min-w-0 flex-1">
								<span class="block truncate text-base font-medium text-ink-gray-8">
									{{ portal.user?.full_name }}
								</span>
								<span class="block truncate text-xs text-ink-gray-5">
									{{ portal.user?.email }}
								</span>
							</span>
							<i class="lucide-chevrons-up-down size-4 shrink-0 text-ink-gray-5" />
						</button>
					</Dropdown>
				</div>
			</Sidebar>
		</template>

		<RouterView :key="route.fullPath" />
	</DesktopShell>
</template>
