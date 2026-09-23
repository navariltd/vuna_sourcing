<script setup lang="ts">
import { Button } from "frappe-ui";
</script>

<template>
	<div
		class="relative flex min-h-[70vh] flex-col items-center justify-center overflow-hidden px-6 text-center"
	>
		<div
			class="pointer-events-none absolute left-1/2 top-1/2 size-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-outline-gray-2"
		></div>

		<div
			class="pointer-events-none absolute left-1/2 top-1/2 size-[300px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-outline-gray-2"
		></div>

		<div class="relative mb-6">
			<div
				class="absolute inset-0 scale-125 rounded-full bg-surface-gray-2/60 blur-2xl"
			></div>

			<div
				class="relative flex size-24 items-center justify-center rounded-3xl border border-outline-gray-2 bg-surface-white shadow-sm"
			>
				<i class="lucide-compass size-11 text-ink-gray-6" aria-hidden="true" />
			</div>
		</div>

		<div
			class="select-none text-[96px] font-bold leading-none tracking-[-0.07em] text-ink-gray-9 sm:text-[120px]"
		>
			404
		</div>

		<div class="relative mt-4 max-w-md">
			<h1 class="text-xl font-semibold tracking-tight text-ink-gray-9">
				Looks like you've lost your way.
			</h1>

			<p class="mt-2 text-p-base leading-6 text-ink-gray-6">
				The page you're looking for doesn't exist, has moved, or you don't have access to
				it.
			</p>
		</div>

		<div class="relative mt-7">
			<Button variant="solid" label="Back to portal" :route="{ name: 'Home' }" />
		</div>

		<p class="relative mt-6 text-xs text-ink-gray-5">
			No need to panic. Your portal is right this way.
		</p>
	</div>
</template>
