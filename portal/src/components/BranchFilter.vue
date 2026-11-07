<script setup lang="ts">
import { computed } from "vue";
import { MultiSelect } from "frappe-ui";
import { usePortalStore } from "@/stores/portal";
import { useBranchSearch } from "@/composables/useBranchSearch";

const SEARCH_FROM = 8;

const portal = usePortalStore();

const branches = computed(() => portal.activeBranches);
const { query, options, hiddenCount, titleOf } = useBranchSearch(
	branches,
	computed(() => portal.selectedBranches)
);

const selected = computed({
	get: () => portal.selectedBranches,
	set: (names: Array<string | number>) => portal.setSelectedBranches(names.map(String)),
});

const summary = computed(() => {
	const chosen = portal.selectedBranches;
	if (!chosen.length) return portal.isBranchLimited ? "All my branches" : "All branches";
	if (chosen.length === 1) return titleOf(chosen[0]!);
	return `${chosen.length} branches`;
});

const onlyBranch = computed(() =>
	portal.isBranchLimited && branches.value.length === 1 ? branches.value[0] : null
);
</script>

<template>
	<div v-if="branches.length > 1 || portal.branchesLoading">
		<p class="px-1 pb-1 pt-1 text-xs uppercase tracking-wide text-ink-gray-5">Branch</p>
		<MultiSelect
			v-model="selected"
			v-model:query="query"
			class="w-full"
			variant="outline"
			aria-label="Branches"
			placeholder="Search branches"
			:options="options"
			:filterable="false"
			:loading="portal.branchesLoading"
			:disabled="portal.branchesLoading"
			:hide-search="branches.length < SEARCH_FROM"
			empty-text="No branch matches"
		>
			<template #prefix>
				<i class="lucide-map-pin size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
			</template>
			<template #summary>
				<span class="truncate text-ink-gray-8">
					{{ portal.branchesLoading ? "Loading branches…" : summary }}
				</span>
			</template>
			<template v-if="hiddenCount" #search-suffix>
				<span class="shrink-0 whitespace-nowrap text-xs text-ink-gray-5">
					+{{ hiddenCount }} more, keep typing
				</span>
			</template>
		</MultiSelect>
	</div>
	<div
		v-else-if="onlyBranch"
		class="flex min-w-0 items-center gap-1.5 px-1 text-sm text-ink-gray-6"
		:title="onlyBranch.title"
	>
		<i class="lucide-map-pin size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
		<span class="truncate">{{ onlyBranch.title }}</span>
	</div>
</template>
