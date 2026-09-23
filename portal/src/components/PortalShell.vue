<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import {
	Avatar,
	BottomSheet,
	Button,
	DesktopShell,
	Dropdown,
	MobileNav,
	MobileNavItem,
	MobileShell,
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarLabel,
	SidebarRail,
	SidebarRailItem,
} from "frappe-ui";
import { useIsMobile } from "@/composables/useViewport";
import { partyKey, usePortalStore } from "@/stores/portal";
import type { Party } from "@/stores/portal";
import { session } from "@/data/session";
import { PARTY_COPY } from "@/data/parties";
import PartySwitcher from "@/components/PartySwitcher.vue";

const portal = usePortalStore();
const route = useRoute();

const showRail = computed(() => portal.parties.length > 1);

const activeKey = computed(() => (portal.activeParty ? partyKey(portal.activeParty) : null));

const headerTitle = computed(() =>
	portal.isMultiParty ? "Sourcing Portal" : portal.activeParty?.title ?? "Sourcing Portal"
);

const headerSubtitle = computed(() => {
	if (portal.isMultiParty) return portal.user?.full_name;
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

const isMobile = useIsMobile();

const accountSheet = ref(false);

const canApply = computed(() => portal.canApply && portal.partyTypesToJoin.length > 0);

const accountActions = computed(() =>
	userMenu.value.filter((item) => !item.condition || item.condition())
);

function runAccountAction(action: () => void) {
	accountSheet.value = false;
	action();
}
</script>

<template>
	<MobileShell v-if="isMobile">
		<PartySwitcher
			class="sticky top-0 z-10 border-b border-outline-gray-2 bg-surface-white px-4 py-2"
		/>

		<RouterView :key="route.fullPath" />

		<template #nav>
			<MobileNav>
				<MobileNavItem
					v-if="portal.hasParties"
					label="Overview"
					icon="lucide-layout-dashboard"
					:route="{ name: 'PortalOverview' }"
				/>
				<MobileNavItem
					label="Applications"
					icon="lucide-folder-clock"
					:route="{ name: 'ApplicationList' }"
				/>
				<MobileNavItem
					v-if="canApply"
					label="Apply"
					icon="lucide-file-pen-line"
					:route="{ name: 'ApplicationForm' }"
				/>
				<MobileNavItem label="You" :active="accountSheet" @click="accountSheet = true">
					<Avatar
						:image="portal.user?.image || undefined"
						:label="portal.user?.full_name || '?'"
						size="sm"
					/>
				</MobileNavItem>
			</MobileNav>
		</template>
	</MobileShell>

	<DesktopShell v-else>
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

				<PartySwitcher class="px-2 pb-1" />

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

	<BottomSheet v-if="isMobile" v-model:open="accountSheet" title="Account">
		<div class="px-4 pb-6">
			<div class="flex items-center gap-3">
				<Avatar
					:image="portal.user?.image || undefined"
					:label="portal.user?.full_name || '?'"
					size="lg"
				/>
				<div class="min-w-0">
					<p class="truncate text-base font-medium text-ink-gray-8">
						{{ portal.user?.full_name }}
					</p>
					<p class="truncate text-sm text-ink-gray-5">{{ portal.user?.email }}</p>
				</div>
			</div>

			<div class="mt-4 flex flex-col gap-2">
				<Button
					v-for="action in accountActions"
					:key="action.label"
					:label="action.label"
					:icon-left="action.icon"
					size="md"
					@click="runAccountAction(action.onClick)"
				/>
			</div>
		</div>
	</BottomSheet>
</template>
