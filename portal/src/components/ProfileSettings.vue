<script setup lang="ts">
import { computed } from "vue";
import { Avatar, Badge, Button } from "frappe-ui";
import { session } from "@/data/session";
import { usePortalStore } from "@/stores/portal";

const portal = usePortalStore();

const parties = computed(() => portal.parties);
</script>

<template>
	<div class="flex flex-col gap-4">
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

		<div class="rounded-6 border p-4">
			<p class="text-xs uppercase tracking-wide text-ink-gray-5">Accounts you act for</p>

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
						<span class="truncate text-p-base text-ink-gray-8">{{ party.title }}</span>
					</span>
					<Badge
						class="shrink-0"
						theme="gray"
						variant="subtle"
						:label="party.party_type"
					/>
				</div>
			</div>
		</div>

		<div class="flex sm:justify-end">
			<Button
				class="w-full sm:w-auto"
				variant="subtle"
				theme="red"
				label="Sign out"
				icon-left="lucide-log-out"
				@click="session.logout.submit()"
			/>
		</div>
	</div>
</template>
