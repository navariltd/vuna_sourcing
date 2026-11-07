<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { KeyboardShortcut, Spinner } from "frappe-ui";
import {
	CommandPalette,
	CommandPaletteEmpty,
	CommandPaletteFooter,
	CommandPaletteGroup,
	CommandPaletteInput,
	CommandPaletteItem,
	CommandPaletteList,
} from "frappe-ui/experimental";
import { ACCENTS } from "@/data/accents";
import type { DocumentLook } from "@/data/accents";
import { money, shortDate } from "@/data/purchase";
import { MIN_SEARCH, SEARCH_GROUPS, searchDocuments } from "@/data/search";
import type { SearchGroup, SearchResult } from "@/data/search";
import { errorText } from "@/data/orders";
import { usePortalStore } from "@/stores/portal";
import { isOk } from "@/types/api";

export interface SearchPageLink {
	label: string;
	route: string;
	look: DocumentLook;
}

const props = defineProps<{ pages: SearchPageLink[] }>();
const open = defineModel<boolean>("open", { default: false });

const SEARCH_DELAY = 250;

const portal = usePortalStore();
const router = useRouter();

const query = ref("");
const groups = ref<SearchGroup[]>([]);
const searching = ref(false);
const searchError = ref<string | null>(null);
let request = 0;
let timer: ReturnType<typeof setTimeout> | undefined;

const term = computed(() => query.value.trim());
const tooShort = computed(() => term.value.length < MIN_SEARCH);

const matchingPages = computed(() => {
	const needle = term.value.toLowerCase();
	return needle
		? props.pages.filter((page) => page.label.toLowerCase().includes(needle))
		: props.pages;
});

async function run(value: string) {
	const party = portal.activeParty;
	const current = ++request;
	if (!party || value.length < MIN_SEARCH) {
		groups.value = [];
		searching.value = false;
		return;
	}

	searching.value = true;
	searchError.value = null;
	try {
		const response = await searchDocuments(party.party_type, party.name, value);
		if (current !== request) return;
		if (isOk(response)) groups.value = response.data.groups;
		else searchError.value = response.message || "Search is not available right now.";
	} catch (error) {
		if (current === request)
			searchError.value = errorText(error, "Search is not available right now.");
	} finally {
		if (current === request) searching.value = false;
	}
}

watch(term, (value) => {
	clearTimeout(timer);
	if (value.length < MIN_SEARCH) {
		run("");
		return;
	}
	searching.value = true;
	timer = setTimeout(() => run(value), SEARCH_DELAY);
});

watch(open, (isOpen) => {
	if (isOpen) return;
	clearTimeout(timer);
	request++;
	query.value = "";
	groups.value = [];
	searchError.value = null;
	searching.value = false;
});

onBeforeUnmount(() => clearTimeout(timer));

type Pick = { kind: "page"; route: string } | { kind: "document"; route: string; name: string };

function select(value: unknown) {
	const picked = value as Pick;
	if (picked.kind === "page") router.push({ name: picked.route });
	else router.push({ name: picked.route, params: { name: picked.name } });
}

function detailOf(group: SearchGroup, row: SearchResult) {
	const parts: string[] = [];
	const label = SEARCH_GROUPS[group.doctype].detail;
	if (row.detail) parts.push(label ? `${label} ${row.detail}` : row.detail);
	if (row.date) parts.push(shortDate(row.date));
	if (row.status) parts.push(row.status);
	return parts.join(" · ");
}
</script>

<template>
	<CommandPalette
		v-model:open="open"
		v-model:query="query"
		:filterable="false"
		title="Search the portal"
		@select="select"
	>
		<CommandPaletteInput
			:placeholder="`Search ${
				portal.activeParty?.title ?? 'your account'
			}: order, invoice or PO number`"
		>
			<template v-if="searching" #suffix>
				<Spinner class="size-4 text-ink-gray-5" />
			</template>
		</CommandPaletteInput>

		<CommandPaletteList>
			<CommandPaletteGroup v-if="matchingPages.length" label="Go to">
				<CommandPaletteItem
					v-for="page in matchingPages"
					:key="page.route"
					:value="{ kind: 'page', route: page.route }"
					:label="page.label"
				>
					<template #prefix>
						<span
							class="grid size-6 shrink-0 place-items-center rounded-5"
							:class="ACCENTS[page.look.accent].tile"
						>
							<i :class="[page.look.icon, 'size-3.5']" aria-hidden="true" />
						</span>
					</template>
					{{ page.label }}
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup
				v-for="group in groups"
				:key="group.doctype"
				:label="SEARCH_GROUPS[group.doctype].label"
			>
				<CommandPaletteItem
					v-for="row in group.results"
					:key="`${group.doctype}::${row.name}`"
					:value="{
						kind: 'document',
						route: SEARCH_GROUPS[group.doctype].route,
						name: row.name,
					}"
					:label="row.name"
				>
					<template #prefix>
						<span
							class="grid size-6 shrink-0 place-items-center rounded-5"
							:class="ACCENTS[SEARCH_GROUPS[group.doctype].look.accent].tile"
						>
							<i
								:class="[SEARCH_GROUPS[group.doctype].look.icon, 'size-3.5']"
								aria-hidden="true"
							/>
						</span>
					</template>
					<span class="flex min-w-0 flex-col">
						<span class="truncate text-base text-ink-gray-9">{{ row.name }}</span>
						<span class="truncate text-p-xs text-ink-gray-5">{{
							detailOf(group, row)
						}}</span>
					</span>
					<template v-if="row.amount != null" #suffix>
						<span class="text-p-sm tabular-nums text-ink-gray-6">
							{{ money(row.amount, row.currency) }}
						</span>
					</template>
				</CommandPaletteItem>
			</CommandPaletteGroup>
		</CommandPaletteList>

		<CommandPaletteEmpty>
			<span v-if="searchError" class="text-ink-red-4">{{ searchError }}</span>
			<span v-else-if="searching">Searching…</span>
			<span v-else-if="tooShort">Type at least {{ MIN_SEARCH }} characters to search.</span>
			<span v-else>Nothing matches “{{ term }}”. Try an order, invoice or PO number.</span>
		</CommandPaletteEmpty>

		<CommandPaletteFooter>
			<span class="flex items-center gap-3 text-p-xs text-ink-gray-5">
				<span class="flex items-center gap-1"
					><KeyboardShortcut combo="Enter" /> to open</span
				>
				<span class="flex items-center gap-1"
					><KeyboardShortcut combo="Escape" /> to close</span
				>
			</span>
		</CommandPaletteFooter>
	</CommandPalette>
</template>
