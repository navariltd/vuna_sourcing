<script setup lang="ts">
import { computed, ref } from "vue";
import {
	Avatar,
	Badge,
	Button,
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
import { session } from "@/data/session";
import { usePortalStore } from "@/stores/portal";

const open = defineModel<boolean>("open", { default: false });

const portal = usePortalStore();

const parties = computed(() => portal.parties);

const tab = ref("profile");
</script>

<template>
	<SettingsDialog v-model:open="open" v-model:tab="tab">
		<SettingsSidebar>
			<SettingsNavGroup label="Account">
				<SettingsNavItem :value="'profile'" icon="lucide-user">Profile</SettingsNavItem>
				<SettingsNavItem :value="'preferences'" icon="lucide-settings-2">
					Preferences
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
					<div class="flex items-center gap-3 rounded-6 border p-4">
						<Avatar
							:image="portal.user?.image || undefined"
							:label="portal.user?.full_name || '?'"
							size="xl"
						/>
						<div class="min-w-0">
							<p class="truncate text-base font-medium text-ink-gray-8">
								{{ portal.user?.full_name }}
							</p>
							<p class="truncate text-p-sm text-ink-gray-5">
								{{ portal.user?.email }}
							</p>
						</div>
					</div>

					<div class="mt-4 rounded-6 border p-4">
						<p class="text-xs uppercase tracking-wide text-ink-gray-5">
							Accounts you act for
						</p>

						<p v-if="!parties.length" class="mt-2 text-p-sm text-ink-gray-5">
							None yet. Once an application is approved it appears here.
						</p>

						<div v-else class="mt-2 divide-y">
							<div
								v-for="party in parties"
								:key="`${party.party_type}-${party.name}`"
								class="flex items-center justify-between gap-3 py-2"
							>
								<span class="flex min-w-0 items-center gap-2">
									<Avatar
										:image="party.image || undefined"
										:label="party.title"
										size="sm"
										shape="square"
									/>
									<span class="truncate text-p-base text-ink-gray-8">{{
										party.title
									}}</span>
								</span>
								<Badge theme="gray" variant="subtle" :label="party.party_type" />
							</div>
						</div>
					</div>

					<div class="mt-4 flex justify-end">
						<Button
							variant="subtle"
							theme="red"
							label="Sign out"
							icon-left="lucide-log-out"
							@click="session.logout.submit()"
						/>
					</div>
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
