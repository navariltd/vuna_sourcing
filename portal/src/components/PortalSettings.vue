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
import CreditSettings from "@/components/CreditSettings.vue";
import { useCreditStatus } from "@/composables/useCreditStatus";
import { usePortalSettings } from "@/composables/usePortalSettings";
import { useIsMobile } from "@/composables/useViewport";
import { usePortalStore } from "@/stores/portal";

const open = defineModel<boolean>("open", { default: false });

const isMobile = useIsMobile();
const portal = usePortalStore();

const { tab } = usePortalSettings();
const credit = useCreditStatus();

const tabs = computed(() => [
	{ value: "profile", label: "Profile", icon: "lucide-user", hint: "Your details and accounts" },
	...(portal.canManageTeam
		? [
				{
					value: "team",
					label: "Team",
					icon: "lucide-users",
					hint: "Invite people and choose their branches",
				},
		  ]
		: []),
	...(credit.enabled.value
		? [
				{
					value: "credit",
					label: "Credit",
					icon: "lucide-wallet",
					hint: "Your credit limit and what you owe",
				},
		  ]
		: []),
	{
		value: "preferences",
		label: "Preferences",
		icon: "lucide-settings-2",
		hint: "Light or dark theme",
	},
]);

const mobileSection = ref<string | null>(null);

const mobileTitle = computed(
	() => tabs.value.find((option) => option.value === mobileSection.value)?.label ?? "Settings"
);

watch(open, (isOpen) => {
	mobileSection.value = isOpen && tab.value !== "profile" ? tab.value : null;
});

watch(
	() => credit.enabled.value,
	(enabled) => {
		if (!enabled && tab.value === "credit") tab.value = "profile";
		if (!enabled && mobileSection.value === "credit") mobileSection.value = null;
	}
);

watch(
	() => portal.canManageTeam,
	(canManage) => {
		if (!canManage && tab.value === "team") tab.value = "profile";
		if (!canManage && mobileSection.value === "team") mobileSection.value = null;
	}
);
</script>

<template>
	<BottomSheet v-if="isMobile" v-model:open="open" :title="mobileTitle">
		<div class="flex flex-col gap-4 px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
			<nav v-if="!mobileSection" aria-label="Settings sections">
				<ul class="divide-y divide-outline-gray-1 overflow-hidden rounded-8 border">
					<li v-for="option in tabs" :key="option.value">
						<button
							type="button"
							class="flex min-h-14 w-full items-center gap-3 px-3 py-2.5 text-left active:bg-surface-gray-2"
							@click="mobileSection = option.value"
						>
							<span
								class="grid size-8 shrink-0 place-items-center rounded-6 bg-surface-gray-2"
								aria-hidden="true"
							>
								<i :class="option.icon" class="size-4 text-ink-gray-7" />
							</span>
							<span class="min-w-0 flex-1">
								<span class="block text-base font-medium text-ink-gray-9">
									{{ option.label }}
								</span>
								<span class="block truncate text-p-sm text-ink-gray-5">
									{{ option.hint }}
								</span>
							</span>
							<i
								class="lucide-chevron-right size-4 text-ink-gray-4"
								aria-hidden="true"
							/>
						</button>
					</li>
				</ul>
			</nav>

			<template v-else>
				<button
					type="button"
					class="-ml-1 flex w-fit items-center gap-1 rounded-6 px-1 py-1 text-base font-medium text-ink-gray-7 active:bg-surface-gray-2"
					@click="mobileSection = null"
				>
					<i class="lucide-chevron-left size-4" aria-hidden="true" />
					All settings
				</button>
				<ProfileSettings v-if="mobileSection === 'profile'" />
				<TeamSettings v-else-if="mobileSection === 'team'" />
				<CreditSettings v-else-if="mobileSection === 'credit'" />
				<div v-else class="flex flex-col gap-2">
					<p class="text-p-sm text-ink-gray-6">
						Choose how the portal looks on this device.
					</p>
					<ThemeSwitcher />
				</div>
			</template>
		</div>
	</BottomSheet>

	<SettingsDialog v-else v-model:open="open" v-model:tab="tab" size="5xl">
		<SettingsSidebar>
			<SettingsNavGroup label="Account">
				<SettingsNavItem :value="'profile'" icon="lucide-user">Profile</SettingsNavItem>
				<SettingsNavItem :value="'preferences'" icon="lucide-settings-2">
					Preferences
				</SettingsNavItem>
			</SettingsNavGroup>
			<SettingsNavGroup
				v-if="portal.canManageTeam || credit.enabled.value"
				:label="portal.activeParty?.title || 'Company'"
			>
				<SettingsNavItem v-if="portal.canManageTeam" :value="'team'" icon="lucide-users">
					Team
				</SettingsNavItem>
				<SettingsNavItem
					v-if="credit.enabled.value"
					:value="'credit'"
					icon="lucide-wallet"
				>
					Credit
				</SettingsNavItem>
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

			<SettingsPanel v-if="credit.enabled.value" :value="'credit'">
				<SettingsHeader
					class="mb-2"
					title="Credit"
					description="Your credit limit, what you owe and what is left."
				/>
				<SettingsBody>
					<CreditSettings />
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
