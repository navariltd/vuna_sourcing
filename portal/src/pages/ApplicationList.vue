<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { Badge, Button, Spinner } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import { myApplications, STATUS_THEME } from "@/data/application";
import type { BadgeTheme } from "@/data/application";
import { partyCopy } from "@/data/parties";
import { usePortalStore } from "@/stores/portal";

const portal = usePortalStore();

onMounted(() => myApplications.fetch());

const router = useRouter();

const isDraft = (row: any) => row.docstatus === 0;
const isReturned = (row: any) =>
	row.docstatus === 1 && row.onboarding_status === "Returned for Correction";

function openDraft(row: any) {
	router.push({ name: "ApplicationForm", query: { name: row.name } });
}

function statusLabel(row: any) {
	if (isDraft(row)) return "Draft";
	return row.onboarding_status || "Submitted";
}

function statusTheme(row: any): BadgeTheme {
	if (isDraft(row)) return "gray";
	return STATUS_THEME[row.onboarding_status] ?? "gray";
}

function formatDate(value: string) {
	return new Date(value).toLocaleDateString(undefined, {
		day: "numeric",
		month: "short",
		year: "numeric",
	});
}
</script>

<template>
	<PageContainer
		wide
		title="My applications"
		subtitle="Every application you have made — as a supplier, a customer, or both."
	>
		<template #actions>
			<Button
				v-if="portal.canApply"
				variant="solid"
				label="New application"
				icon-left="lucide-plus"
				:route="{ name: 'ApplicationForm' }"
			/>
		</template>

		<div
			v-if="myApplications.loading && !myApplications.data"
			class="flex justify-center py-16"
		>
			<Spinner class="size-5" />
		</div>

		<div
			v-else-if="!myApplications.data?.length"
			class="rounded-6 border border-dashed py-16 text-center"
		>
			<p class="text-base font-medium text-ink-gray-7">No applications yet</p>
			<p class="mt-1 text-p-sm text-ink-gray-5">
				Start one and we will guide you through what is needed.
			</p>
			<Button
				v-if="portal.canApply"
				class="mt-4"
				variant="solid"
				label="Start an application"
				:route="{ name: 'ApplicationForm' }"
			/>
		</div>

		<div v-else class="divide-y rounded-6 border">
			<div
				v-for="row in myApplications.data"
				:key="row.name"
				class="flex flex-wrap items-center gap-3 p-4 transition hover:bg-surface-gray-1"
			>
				<RouterLink
					:to="{ name: 'ApplicationDetail', params: { name: row.name } }"
					class="min-w-0 flex-1"
				>
					<p
						class="flex items-center gap-2 truncate text-base font-medium text-ink-gray-8"
					>
						<i
							v-if="partyCopy(row.party_type)"
							:class="[partyCopy(row.party_type)!.icon, 'size-4 shrink-0 text-ink-gray-5']"
						/>
						{{ row.party_name || "Untitled application" }}
					</p>
					<p class="mt-0.5 truncate text-p-sm text-ink-gray-5">
						{{
							row.party_type
								? `As a ${partyCopy(row.party_type)?.noun}`
								: "Not chosen yet"
						}}
						<template v-if="row.onboarding_template">
							· {{ row.onboarding_template }}</template
						>
						· {{ row.name }}
					</p>

					<p
						v-if="isReturned(row) && row.review_remarks"
						class="mt-1.5 line-clamp-2 text-p-sm text-ink-amber-7"
					>
						{{ row.review_remarks }}
					</p>
				</RouterLink>

				<div class="flex shrink-0 items-center gap-2">
					<span class="hidden text-xs text-ink-gray-5 sm:inline">
						{{ formatDate(row.modified) }}
					</span>
					<Badge :theme="statusTheme(row)" variant="subtle" :label="statusLabel(row)" />

					<Button
						v-if="isDraft(row)"
						variant="subtle"
						label="Edit"
						icon-left="lucide-pencil"
						@click="openDraft(row)"
					/>
					<Button
						v-else-if="isReturned(row)"
						variant="solid"
						label="Fix and resubmit"
						icon-left="lucide-rotate-ccw"
						@click="openDraft(row)"
					/>
				</div>
			</div>
		</div>
	</PageContainer>
</template>
