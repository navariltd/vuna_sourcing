<script setup lang="ts">
import { computed } from "vue";
import { Badge, Button, FileUploader, FormControl, toast } from "frappe-ui";
import {
	documentProblems,
	fileExtension,
	fileSize,
	localToday,
	uploadEndpoint,
	uploadProblem,
	uploadedAttachment,
} from "@/data/application";
import type { RequiredDocument } from "@/data/application";

const props = defineProps<{
	document: RequiredDocument;
	docname: string;
	showProblems?: boolean;
}>();

const emit = defineEmits<{
	(e: "update", value: Partial<RequiredDocument>): void;
}>();

const FILE_STYLES: Record<string, string> = {
	pdf: "bg-[#E5484D]",
	png: "bg-[#3E63DD]",
	jpg: "bg-[#3E63DD]",
	jpeg: "bg-[#3E63DD]",
	webp: "bg-[#3E63DD]",
	gif: "bg-[#3E63DD]",
	doc: "bg-[#2F5BB7]",
	docx: "bg-[#2F5BB7]",
	xls: "bg-[#1F7A4D]",
	xlsx: "bg-[#1F7A4D]",
	csv: "bg-[#1F7A4D]",
};

const endpoint = computed(() =>
	uploadEndpoint(props.docname, { documentType: props.document.document_type })
);

const accept = computed(() =>
	(props.document.allowed_file_types ?? [])
		.map((type) => `.${type.toLowerCase().replace(/^\./, "")}`)
		.join(",")
);

const rulesText = computed(() => {
	const types = (props.document.allowed_file_types ?? []).map((type) =>
		type.replace(/^\./, "").toUpperCase()
	);
	const limit = props.document.max_file_size_mb;
	return [types.join(", "), limit ? `up to ${limit} MB` : null].filter(Boolean).join(" · ");
});

const attachedName = computed(() => {
	if (props.document.file_name) return props.document.file_name;
	const url = props.document.attachment;
	return url ? decodeURIComponent(url.split("/").pop() || url) : "";
});

const problems = computed(() => documentProblems(props.document, localToday()));

function iconStyle(name: string) {
	return FILE_STYLES[fileExtension(name)] ?? "bg-surface-gray-7";
}

function iconLabel(name: string) {
	return (fileExtension(name) || "file").slice(0, 4).toUpperCase();
}

function onUploaded(response: unknown) {
	try {
		const file = uploadedAttachment(response);
		emit("update", {
			attachment: file.file_url,
			file_name: file.file_name,
			file_size: file.file_size,
		});
	} catch (error: any) {
		toast.error(error?.message || "The upload did not go through.");
	}
}

function onFailed(error: unknown) {
	const message =
		typeof error === "string"
			? error
			: (error as any)?.messages?.[0] || (error as any)?.message || null;
	if (message) toast.error(message);
}

function removeFile() {
	emit("update", {
		attachment: null,
		file_name: null,
		file_size: null,
		document_number: null,
		issue_date: null,
		expiry_date: null,
	});
}
</script>

<template>
	<div class="rounded-8 border border-outline-gray-2 bg-surface-base p-4">
		<div class="flex flex-wrap items-center gap-2">
			<span class="text-base font-semibold text-ink-gray-9">{{
				document.document_type
			}}</span>
			<Badge
				:theme="document.is_mandatory ? 'red' : 'gray'"
				variant="subtle"
				:label="document.is_mandatory ? 'Required' : 'Optional'"
			/>
			<Badge
				v-if="document.has_expiry"
				theme="gray"
				variant="subtle"
				label="Has expiry date"
			/>
		</div>
		<p v-if="document.description" class="mt-1 text-p-sm text-ink-gray-6">
			{{ document.description }}
		</p>

		<FileUploader
			v-if="!document.attachment"
			:upload-endpoint="endpoint"
			:file-types="accept || undefined"
			:validate-file="(file: File) => uploadProblem(file, document)"
			@success="onUploaded"
			@failure="onFailed"
		>
			<template #default="{ openFileSelector, uploading, progress, uploaded, total, file }">
				<div
					v-if="uploading && file"
					class="mt-3 rounded-8 border border-outline-gray-2 p-3"
					aria-live="polite"
				>
					<div class="flex items-center gap-3">
						<span class="file-icon" :class="iconStyle(file.name)" aria-hidden="true">
							{{ iconLabel(file.name) }}
						</span>
						<div class="min-w-0 flex-1">
							<p class="truncate text-base font-medium text-ink-gray-9">
								{{ file.name }}
							</p>
							<p class="flex items-center gap-1.5 text-p-sm text-ink-gray-6">
								<span class="tabular-nums">
									{{ fileSize(uploaded) }} of {{ fileSize(total || file.size) }}
								</span>
								<span aria-hidden="true">·</span>
								<i
									class="lucide-loader-circle size-3.5 animate-spin"
									aria-hidden="true"
								/>
								Uploading…
							</p>
						</div>
					</div>
					<div class="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-gray-2">
						<div
							class="h-full rounded-full bg-surface-gray-9 transition-[width]"
							:style="{ width: `${progress}%` }"
						/>
					</div>
				</div>

				<button
					v-else
					type="button"
					class="mt-3 flex w-full items-center gap-3 rounded-8 border border-dashed border-outline-gray-3 p-3 text-left transition-colors hover:border-outline-gray-5 hover:bg-surface-gray-1"
					@click="openFileSelector"
				>
					<span
						class="grid size-10 shrink-0 place-items-center rounded-6 bg-surface-gray-2"
					>
						<i class="lucide-upload size-4 text-ink-gray-7" aria-hidden="true" />
					</span>
					<span class="min-w-0">
						<span class="block text-base font-medium text-ink-gray-9"
							>Choose a file</span
						>
						<span v-if="rulesText" class="block text-p-sm text-ink-gray-5">
							{{ rulesText }}
						</span>
					</span>
				</button>
			</template>
		</FileUploader>

		<template v-else>
			<div class="mt-3 flex items-center gap-3 rounded-8 border border-outline-gray-2 p-3">
				<span class="file-icon" :class="iconStyle(attachedName)" aria-hidden="true">
					{{ iconLabel(attachedName) }}
				</span>
				<div class="min-w-0 flex-1">
					<a
						:href="document.attachment!"
						target="_blank"
						class="block truncate text-base font-medium text-ink-gray-9 hover:underline"
					>
						{{ attachedName }}
					</a>
					<p class="flex items-center gap-1.5 text-p-sm text-ink-gray-6">
						<template v-if="document.file_size">
							<span class="tabular-nums">{{ fileSize(document.file_size) }}</span>
							<span aria-hidden="true">·</span>
						</template>
						<i
							class="lucide-circle-check size-3.5 text-ink-green-6"
							aria-hidden="true"
						/>
						Uploaded
					</p>
				</div>
				<Button variant="ghost" :aria-label="`Remove ${attachedName}`" @click="removeFile">
					<template #icon>
						<i class="lucide-x size-4" aria-hidden="true" />
					</template>
				</Button>
			</div>

			<div
				class="mt-3 grid gap-3"
				:class="document.has_expiry ? 'sm:grid-cols-3' : 'sm:grid-cols-2'"
			>
				<FormControl
					type="text"
					label="Reference no (optional)"
					placeholder="Number printed on the document"
					:model-value="document.document_number || ''"
					@update:model-value="emit('update', { document_number: $event || null })"
				/>
				<FormControl
					type="date"
					label="Issue date"
					:max="localToday()"
					:model-value="document.issue_date || ''"
					@update:model-value="emit('update', { issue_date: $event || null })"
				/>
				<FormControl
					v-if="document.has_expiry"
					type="date"
					label="Expiry date"
					required
					:min="document.issue_date || localToday()"
					:model-value="document.expiry_date || ''"
					@update:model-value="emit('update', { expiry_date: $event || null })"
				/>
			</div>
		</template>

		<ul
			v-if="(showProblems || document.attachment) && problems.length"
			class="mt-3 flex flex-col gap-1"
		>
			<li
				v-for="problem in problems"
				:key="problem"
				class="flex items-center gap-1.5 text-p-sm font-medium text-ink-amber-7"
			>
				<i class="lucide-circle-alert size-3.5 shrink-0" aria-hidden="true" />
				{{ problem }}
			</li>
		</ul>
	</div>
</template>

<style scoped>
.file-icon {
	display: grid;
	flex-shrink: 0;
	place-items: center;
	width: 2.5rem;
	height: 2.75rem;
	border-radius: 0.375rem;
	color: white;
	font-size: 0.625rem;
	font-weight: 700;
	letter-spacing: 0.02em;
	clip-path: polygon(0 0, 70% 0, 100% 24%, 100% 100%, 0 100%);
}
</style>
