<script setup lang="ts">
import { computed } from "vue";
import DOMPurify from "dompurify";

const props = defineProps<{ html: string | null | undefined }>();

const clean = computed(() =>
	props.html
		? DOMPurify.sanitize(props.html, {
				USE_PROFILES: { html: true },
				ADD_ATTR: ["target", "rel"],
		  })
		: ""
);
</script>

<template>
	<div
		v-if="clean"
		class="prose-sm max-w-none text-p-base text-ink-gray-7 [&_a]:text-ink-blue-link [&_a]:underline [&_li]:my-0.5 [&_ol]:list-decimal [&_ol]:ps-5 [&_p]:my-1 [&_table]:w-full [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:px-2 [&_th]:py-1 [&_ul]:list-disc [&_ul]:ps-5"
		v-html="clean"
	/>
</template>
