<script setup lang="ts">
import { ref } from "vue";
import { Breadcrumbs, Tooltip, toast } from "frappe-ui";
import type { RouteLocationRaw } from "vue-router";
import { ACCENTS } from "@/data/accents";
import type { DocumentLook } from "@/data/accents";

const props = defineProps<{
	title: string;
	breadcrumbs?: { label: string; route?: RouteLocationRaw }[];
	wide?: boolean;
	copy?: string;
	look?: DocumentLook;
	stickyHeader?: boolean;
	fluid?: boolean;
}>();

const copied = ref(false);

function copyWithSelection(text: string) {
	const field = document.createElement("textarea");
	field.value = text;
	field.setAttribute("readonly", "");
	field.style.position = "fixed";
	field.style.opacity = "0";
	document.body.appendChild(field);
	field.select();
	const done = document.execCommand("copy");
	field.remove();
	return done;
}

async function copyValue() {
	if (!props.copy) return;

	let done = false;
	try {
		await navigator.clipboard.writeText(props.copy);
		done = true;
	} catch {
		done = copyWithSelection(props.copy);
	}

	if (!done) {
		toast.error("Could not copy. Select the number and copy it instead.");
		return;
	}

	toast.success(`Copied ${props.copy}`);
	copied.value = true;
	setTimeout(() => (copied.value = false), 1500);
}
</script>

<template>
	<div
		class="mx-auto w-full px-4 py-6 sm:px-6 sm:py-8"
		:class="fluid ? 'max-w-[1720px]' : wide ? 'max-w-7xl' : 'max-w-4xl'"
	>
		<header
			v-if="breadcrumbs?.length"
			class="mb-6 flex flex-wrap items-center justify-between gap-3"
			:class="
				stickyHeader
					? 'sm:sticky sm:top-0 sm:z-20 sm:-mx-6 sm:-mt-4 sm:border-b sm:border-outline-gray-1 sm:bg-surface-base sm:px-6 sm:pb-3 sm:pt-4'
					: ''
			"
		>
			<div class="min-w-0">
				<div class="flex min-w-0 items-center gap-1">
					<span
						v-if="look"
						class="mr-1.5 grid size-7 shrink-0 place-items-center rounded-5"
						:class="ACCENTS[look.accent].tile"
					>
						<i :class="[look.icon, 'size-4']" aria-hidden="true" />
					</span>
					<Breadcrumbs :items="breadcrumbs" class="min-w-0" />
					<Tooltip v-if="copy" :text="copied ? 'Copied' : `Copy ${copy}`">
						<button
							type="button"
							class="grid size-7 shrink-0 place-items-center rounded-4 text-ink-gray-5 transition-colors hover:bg-surface-gray-2 hover:text-ink-gray-8"
							:aria-label="`Copy ${copy}`"
							@click="copyValue"
						>
							<i
								:class="[
									copied ? 'lucide-check text-ink-green-6' : 'lucide-copy',
									'size-4',
								]"
							/>
						</button>
					</Tooltip>
				</div>
			</div>
			<div class="flex flex-wrap items-center gap-2">
				<slot name="actions" />
			</div>
		</header>

		<header v-else class="mb-6 flex flex-wrap items-start justify-between gap-3">
			<div class="flex min-w-0 items-center gap-3">
				<span
					v-if="look"
					class="grid size-10 shrink-0 place-items-center rounded-6"
					:class="ACCENTS[look.accent].tile"
				>
					<i :class="[look.icon, 'size-5']" aria-hidden="true" />
				</span>
				<div class="min-w-0">
					<h1 class="truncate text-xl font-semibold text-ink-gray-9">{{ title }}</h1>
				</div>
			</div>
			<div class="flex shrink-0 items-center gap-2">
				<slot name="actions" />
			</div>
		</header>

		<slot />
	</div>
</template>
