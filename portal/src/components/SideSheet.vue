<script setup lang="ts">
import { Button } from "frappe-ui";
import {
	DialogClose,
	DialogContent,
	DialogDescription,
	DialogOverlay,
	DialogPortal,
	DialogRoot,
	DialogTitle,
} from "reka-ui";

const open = defineModel<boolean>("open", { default: false });

defineProps<{ title: string; description?: string }>();
</script>

<template>
	<DialogRoot v-model:open="open">
		<DialogPortal>
			<DialogOverlay
				class="side-sheet-overlay fixed inset-0 z-50 bg-black-overlay-200 dark:bg-black-overlay-700"
			/>
			<DialogContent
				class="side-sheet fixed inset-y-0 right-0 z-50 flex w-full flex-col bg-surface-base shadow-2xl outline-none sm:w-[460px] sm:max-w-[92vw] sm:rounded-l-[12px]"
			>
				<header
					class="flex shrink-0 items-start justify-between gap-3 border-b border-outline-gray-1 px-4 pb-3 pt-[max(1rem,env(safe-area-inset-top))]"
				>
					<div class="min-w-0">
						<DialogTitle
							class="flex items-center gap-2 text-lg font-semibold text-ink-gray-9"
						>
							{{ title }}
							<slot name="badge" />
						</DialogTitle>
						<DialogDescription
							v-if="description"
							class="mt-0.5 text-p-sm text-ink-gray-6"
						>
							{{ description }}
						</DialogDescription>
					</div>
					<DialogClose as-child>
						<Button variant="ghost" icon="lucide-x" aria-label="Close" />
					</DialogClose>
				</header>
				<div
					class="flex min-h-0 flex-1 flex-col px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3"
				>
					<slot />
				</div>
			</DialogContent>
		</DialogPortal>
	</DialogRoot>
</template>

<style scoped>
.side-sheet[data-state="open"] {
	animation: sheet-in 320ms cubic-bezier(0.32, 0.72, 0, 1);
}

.side-sheet[data-state="closed"] {
	animation: sheet-out 240ms cubic-bezier(0.32, 0.72, 0, 1);
}

.side-sheet-overlay[data-state="open"] {
	animation: fade-in 240ms ease-out;
}

.side-sheet-overlay[data-state="closed"] {
	animation: fade-out 200ms ease-in;
}

@keyframes sheet-in {
	from {
		transform: translateX(100%);
	}
	to {
		transform: translateX(0);
	}
}

@keyframes sheet-out {
	from {
		transform: translateX(0);
	}
	to {
		transform: translateX(100%);
	}
}

@keyframes fade-in {
	from {
		opacity: 0;
	}
	to {
		opacity: 1;
	}
}

@keyframes fade-out {
	from {
		opacity: 1;
	}
	to {
		opacity: 0;
	}
}

@media (prefers-reduced-motion: reduce) {
	.side-sheet[data-state],
	.side-sheet-overlay[data-state] {
		animation-duration: 1ms;
	}
}
</style>
