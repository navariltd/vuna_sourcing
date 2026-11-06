<script setup lang="ts">
import { computed } from "vue";
import { MultiSelect } from "frappe-ui";
import { usePortalStore } from "@/stores/portal";
import { useBranchSearch } from "@/composables/useBranchSearch";

const SEARCH_FROM = 8;

const model = defineModel<string[]>({ default: () => [] });

defineProps<{ label?: string; description?: string }>();

const portal = usePortalStore();
const branches = computed(() => portal.activeBranches);
const { query, options, hiddenCount, titleOf } = useBranchSearch(branches, model);

const selected = computed({
	get: () => model.value,
	set: (names: Array<string | number>) => (model.value = names.map(String)),
});

const summary = computed(() => {
	if (!model.value.length) return "Every branch";
	if (model.value.length === 1) return titleOf(model.value[0]!);
	return `${model.value.length} branches`;
});
</script>

<template>
	<MultiSelect
		v-model="selected"
		v-model:query="query"
		class="w-full"
		:label="label"
		:description="description"
		placeholder="Search branches"
		:options="options"
		:filterable="false"
		:loading="portal.branchesLoading"
		:hide-search="branches.length < SEARCH_FROM"
		empty-text="No branch matches"
	>
		<template #prefix>
			<i class="lucide-map-pin size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
		</template>
		<template #summary>
			<span class="truncate text-ink-gray-8">{{ summary }}</span>
		</template>
		<template v-if="hiddenCount" #search-suffix>
			<span class="shrink-0 whitespace-nowrap text-xs text-ink-gray-5">
				+{{ hiddenCount }} more, keep typing
			</span>
		</template>
	</MultiSelect>
</template>
