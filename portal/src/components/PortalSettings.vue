<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
	BottomSheet,
	SettingsBody,
	SettingsContent,
	SettingsDialog,
	SettingsHeader,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsPanel,
	SettingsSidebar,
} from "frappe-ui";
import { ThemeSwitcher } from "frappe-ui/experimental";
import ProfileSettings from "@/components/ProfileSettings.vue";
import TeamSettings from "@/components/TeamSettings.vue";
import { useIsMobile } from "@/composables/useViewport";
import { usePortalStore } from "@/stores/portal";

const open = defineModel<boolean>("open", { default: false });

const isMobile = useIsMobile();
const portal = usePortalStore();

const tab = ref("profile");

const tabs = computed(() => [
	{ value: "profile", label: "Profile", icon: "lucide-user" },
	...(portal.canManageTeam ? [{ value: "team", label: "Team", icon: "lucide-users" }] : []),
	{ value: "preferences", label: "Preferences", icon: "lucide-settings-2" },
]);

watch(
	() => portal.canManageTeam,
	(canManage) => {
		if (!canManage && tab.value === "team") tab.value = "profile";
	}
);
</script>

<template>
	<BottomSheet v-if="isMobile" v-model:open="open" title="Settings">
		<div class="flex flex-col gap-4 px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
			<div
				class="grid rounded-8 bg-surface-gray-2 p-1"
				:class="tabs.length === 3 ? 'grid-cols-3' : 'grid-cols-2'"
				role="tablist"
			>
				<button
					v-for="option in tabs"
					:key="option.value"
					type="button"
					role="tab"
					class="flex h-9 items-center justify-center gap-1.5 rounded-6 text-base font-medium transition-colors"
					:class="
						tab === option.value
							? 'bg-surface-base text-ink-gray-9 shadow-sm'
							: 'text-ink-gray-6'
					"
					:aria-selected="tab === option.value"
					@click="tab = option.value"
				>
					<i :class="option.icon" class="size-4" aria-hidden="true" />
					{{ option.label }}
				</button>
			</div>

			<ProfileSettings v-if="tab === 'profile'" />
			<TeamSettings v-else-if="tab === 'team'" />
			<div v-else class="flex flex-col gap-2">
				<p class="text-p-sm text-ink-gray-6">
					Choose how the portal looks on this device.
				</p>
				<ThemeSwitcher />
			</div>
		</div>
	</BottomSheet>

	<SettingsDialog v-else v-model:open="open" v-model:tab="tab">
		<SettingsSidebar>
			<SettingsNavGroup label="Account">
				<SettingsNavItem :value="'profile'" icon="lucide-user">Profile</SettingsNavItem>
				<SettingsNavItem :value="'preferences'" icon="lucide-settings-2">
					Preferences
				</SettingsNavItem>
			</SettingsNavGroup>
			<SettingsNavGroup
				v-if="portal.canManageTeam"
				:label="portal.activeParty?.title || 'Company'"
			>
				<SettingsNavItem :value="'team'" icon="lucide-users">Team</SettingsNavItem>
			</SettingsNavGroup>
		</SettingsSidebar>

		<SettingsContent>
			<SettingsPanel :value="'profile'">
				<SettingsHeader
					class="mb-2"
					title="Profile"
					description="How we know you and what you act for."
				/>
				<SettingsBody>
					<ProfileSettings />
				</SettingsBody>
			</SettingsPanel>

			<SettingsPanel v-if="portal.canManageTeam" :value="'team'">
				<SettingsHeader class="mb-2" title="Team" />
				<SettingsBody>
					<TeamSettings />
				</SettingsBody>
			</SettingsPanel>

			<SettingsPanel :value="'preferences'">
				<SettingsHeader title="Preferences" />
				<SettingsBody>
					<ThemeSwitcher />
				</SettingsBody>
			</SettingsPanel>
		</SettingsContent>
	</SettingsDialog>
</template>
