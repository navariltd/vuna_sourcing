<script setup lang="ts">
import { computed } from "vue";
import { Badge, Button, FileUploader, FormControl, Spinner } from "frappe-ui";
import { attachmentUploadUrl } from "@/data/application";
import type { RequiredDocument } from "@/data/application";

const props = defineProps<{
	document: RequiredDocument;
	docname: string;
	fileTypes?: string;
}>();

const emit = defineEmits<{
	(e: "update", value: Partial<RequiredDocument>): void;
}>();

const attached = computed(() => !!props.document.attachment);

const uploadEndpoint = computed(() => attachmentUploadUrl(props.document.document_type));

const fileName = computed(() => {
	const url = props.document.attachment;
	if (!url) return "";
	return decodeURIComponent(url.split("/").pop() || url);
});

function onUploaded(file: { file_url: string }) {
	emit("update", { attachment: file.file_url });
}

function removeFile() {
	emit("update", { attachment: null });
}
</script>

<template>
	<div
		class="rounded-6 border p-4"
		:class="attached ? 'border-outline-green-2 bg-surface-green-1' : 'bg-surface-base'"
	>
		<div class="flex items-start justify-between gap-3">
			<div class="min-w-0">
				<div class="flex flex-wrap items-center gap-2">
					<span class="text-base font-medium text-ink-gray-8">
						{{ document.document_type }}
					</span>
					<Badge
						v-if="document.is_mandatory"
						theme="red"
						variant="subtle"
						label="Required"
					/>
					<Badge v-else theme="gray" variant="subtle" label="Optional" />
					<Badge v-if="attached" theme="green" variant="subtle" label="Attached" />
				</div>
				<p v-if="document.description" class="mt-1 text-p-sm text-ink-gray-6">
					{{ document.description }}
				</p>
			</div>

			<FileUploader
				v-if="!attached"
				:doctype="'Party Onboarding Request'"
				:docname="docname"
				:upload-endpoint="uploadEndpoint"
				:file-types="fileTypes"
				@success="onUploaded"
			>
				<template #default="{ openFileSelector, uploading, progress }">
					<Button
						:loading="uploading"
						:label="uploading ? `${progress}%` : 'Upload'"
						icon-left="lucide-upload"
						@click="openFileSelector"
					/>
				</template>
			</FileUploader>

			<Button
				v-else
				variant="ghost"
				icon-left="lucide-trash-2"
				label="Remove"
				@click="removeFile"
			/>
		</div>

		<p v-if="attached" class="mt-2 truncate text-p-sm text-ink-gray-6">
			<a :href="document.attachment!" target="_blank" class="underline">{{ fileName }}</a>
		</p>

		<div v-if="attached" class="mt-3 grid gap-3 sm:grid-cols-3">
			<FormControl
				type="text"
				label="Reference no"
				:model-value="document.document_number || ''"
				@update:model-value="emit('update', { document_number: $event })"
			/>
			<FormControl
				type="date"
				label="Issue date"
				:model-value="document.issue_date || ''"
				@update:model-value="emit('update', { issue_date: $event })"
			/>
			<FormControl
				type="date"
				label="Expiry date"
				:model-value="document.expiry_date || ''"
				@update:model-value="emit('update', { expiry_date: $event })"
			/>
		</div>
	</div>
</template>
