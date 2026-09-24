<script setup lang="ts">
import { Badge } from "frappe-ui";
import type { BadgeTheme } from "@/data/application";
import { money, shortDate } from "@/data/purchase";
import type { ReturnNote } from "@/data/purchase";

defineProps<{
	title: string;
	notes: ReturnNote[];
	currency: string | null;
	detailRoute: string;
	statusTheme: Record<string, BadgeTheme>;
}>();
</script>

<template>
	<div v-if="notes.length" class="rounded-6 border p-4">
		<p class="text-xs uppercase tracking-wide text-ink-gray-5">{{ title }}</p>

		<div class="mt-2 divide-y">
			<RouterLink
				v-for="note in notes"
				:key="note.name"
				:to="{ name: detailRoute, params: { name: note.name } }"
				class="flex flex-wrap items-center justify-between gap-2 py-2 hover:bg-surface-gray-1"
			>
				<span class="text-p-base text-ink-gray-8">
					{{ note.name }}
					<span class="text-ink-gray-5">· {{ shortDate(note.posting_date) }}</span>
				</span>
				<span class="flex items-center gap-2">
					<span class="text-p-base font-medium text-ink-gray-8">
						{{ money(note.grand_total, currency) }}
					</span>
					<Badge
						:theme="statusTheme[note.status] || 'gray'"
						variant="subtle"
						:label="note.status"
					/>
				</span>
			</RouterLink>
		</div>
	</div>
</template>
