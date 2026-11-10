<script setup lang="ts">
import {
	AccordionContent,
	AccordionHeader,
	AccordionItem,
	AccordionRoot,
	AccordionTrigger,
} from "reka-ui";

defineProps<{ question: string; answer: string; icon?: string }>();
</script>

<template>
	<AccordionRoot type="single" collapsible class="rounded-6 border border-outline-gray-2">
		<AccordionItem value="explainer">
			<AccordionHeader as="h2">
				<AccordionTrigger
					class="group flex w-full items-center gap-2.5 rounded-6 px-3 py-2.5 text-left text-base font-medium text-ink-gray-8 transition-colors hover:bg-surface-gray-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-4"
				>
					<i
						:class="icon || 'lucide-circle-help'"
						class="size-4 shrink-0 text-ink-gray-5"
						aria-hidden="true"
					/>
					<span class="flex-1">{{ question }}</span>
					<i
						class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5 transition-transform duration-200 group-data-[state=open]:rotate-180"
						aria-hidden="true"
					/>
				</AccordionTrigger>
			</AccordionHeader>
			<AccordionContent class="explainer-content overflow-hidden">
				<p class="px-3 pb-3 pl-9 text-p-sm text-ink-gray-6">{{ answer }}</p>
			</AccordionContent>
		</AccordionItem>
	</AccordionRoot>
</template>

<style scoped>
.explainer-content[data-state="open"] {
	animation: explainer-open 200ms ease-out;
}
.explainer-content[data-state="closed"] {
	animation: explainer-close 160ms ease-in;
}
@keyframes explainer-open {
	from {
		height: 0;
	}
	to {
		height: var(--reka-accordion-content-height);
	}
}
@keyframes explainer-close {
	from {
		height: var(--reka-accordion-content-height);
	}
	to {
		height: 0;
	}
}
@media (prefers-reduced-motion: reduce) {
	.explainer-content[data-state] {
		animation: none;
	}
}
</style>
