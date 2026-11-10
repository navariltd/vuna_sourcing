<script setup lang="ts">
import { computed } from "vue";
import { Badge, Button, FileUploader, toast } from "frappe-ui";
import { injectOrderDraft } from "@/composables/useOrderDraft";
import { fileExtension, fileSize, uploadedAttachment } from "@/data/application";
import { poDocumentEndpoint } from "@/data/orders";

const draft = injectOrderDraft();

const rules = computed(() => draft.poRules.value);
const required = computed(() => !!rules.value?.required);

const endpoint = computed(() =>
	draft.customer.value ? poDocumentEndpoint(draft.customer.value) : ""
);

const types = computed(() => (rules.value?.file_types ?? []).map((type) => type.toLowerCase()));

const accept = computed(() => types.value.map((type) => `.${type}`).join(","));

const rulesText = computed(() =>
	[
		types.value.map((type) => type.toUpperCase()).join(", "),
		rules.value?.max_file_size_mb ? `up to ${rules.value.max_file_size_mb} MB` : null,
	]
		.filter(Boolean)
		.join(" · ")
);

function problem(file: File): string | null {
	const extension = fileExtension(file.name);
	if (types.value.length && !types.value.includes(extension)) {
		return `Attach the LPO as ${types.value.map((type) => type.toUpperCase()).join(", ")}.`;
	}
	const limit = Number(rules.value?.max_file_size_mb || 0);
	if (limit && file.size > limit * 1024 * 1024) {
		return `This file is ${fileSize(file.size)}. The limit is ${limit} MB.`;
	}
	return null;
}

function onUploaded(response: unknown) {
	try {
		const file = uploadedAttachment(response);
		draft.poDocument.value = { file_url: file.file_url, file_name: file.file_name };
		toast.success("LPO attached.");
	} catch (error) {
		toast.error((error as Error).message);
	}
}

function onFailed(error: unknown) {
	const message = error instanceof Error ? error.message : null;
	toast.error(message || "The upload did not go through. Try again.");
}
</script>

<template>
	<div class="flex flex-col gap-1.5">
		<div class="flex items-center gap-2">
			<span class="text-xs text-ink-gray-5">LPO document</span>
			<Badge v-if="required" theme="amber" size="sm" label="Required to send" />
			<span v-else class="text-xs text-ink-gray-5">(optional)</span>
		</div>

		<div
			v-if="draft.poDocument.value"
			class="flex items-center gap-2.5 rounded-6 border border-outline-gray-2 bg-surface-base p-2.5"
		>
			<span
				class="grid size-8 shrink-0 place-items-center rounded-5 bg-surface-gray-2 text-[10px] font-bold uppercase text-ink-gray-7"
				aria-hidden="true"
			>
				{{ fileExtension(draft.poDocument.value.file_name) || "file" }}
			</span>
			<a
				:href="draft.poDocument.value.file_url"
				target="_blank"
				rel="noopener"
				class="min-w-0 flex-1 truncate text-base font-medium text-ink-gray-9 underline-offset-2 hover:underline"
			>
				{{ draft.poDocument.value.file_name }}
			</a>
			<Button
				size="sm"
				variant="ghost"
				icon="lucide-x"
				aria-label="Remove the LPO document"
				@click="draft.poDocument.value = null"
			/>
		</div>

		<FileUploader
			v-else-if="endpoint"
			:upload-endpoint="endpoint"
			:file-types="accept || undefined"
			:validate-file="problem"
			@success="onUploaded"
			@failure="onFailed"
		>
			<template #default="{ openFileSelector, uploading, progress }">
				<button
					type="button"
					class="flex w-full items-center gap-2.5 rounded-6 border border-dashed p-2.5 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-4"
					:class="
						required
							? 'border-outline-amber-4 bg-surface-base hover:bg-surface-amber-1'
							: 'border-outline-gray-3 bg-surface-base hover:bg-surface-gray-1'
					"
					:disabled="uploading"
					@click="openFileSelector"
				>
					<span
						class="grid size-8 shrink-0 place-items-center rounded-5 bg-surface-gray-2"
						aria-hidden="true"
					>
						<i
							:class="
								uploading
									? 'lucide-loader-circle animate-spin'
									: 'lucide-paperclip'
							"
							class="size-4 text-ink-gray-7"
						/>
					</span>
					<span class="min-w-0">
						<span class="block text-base font-medium text-ink-gray-9">
							{{
								uploading
									? `Uploading… ${Math.round(progress)}%`
									: "Attach your LPO"
							}}
						</span>
						<span v-if="rulesText" class="block text-p-xs text-ink-gray-5">
							{{ rulesText }}
						</span>
					</span>
				</button>
			</template>
		</FileUploader>
	</div>
</template>
