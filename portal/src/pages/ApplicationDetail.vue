<script setup lang="ts">
import { computed, onMounted } from "vue";
import { Avatar, Badge, Button, Spinner } from "frappe-ui";
import PageContainer from "@/components/PageContainer.vue";
import {
	createApplicationResource,
	fullName,
	oneLineAddress,
	STATUS_THEME,
} from "@/data/application";
import type { Application, ApplicationAddress, BadgeTheme } from "@/data/application";
import { partyCopy } from "@/data/parties";

const props = defineProps<{ name: string }>();

const application = createApplicationResource();

onMounted(() => application.fetch({ name: props.name }));

const doc = computed<Application | null>(() => application.data);
const copy = computed(() => partyCopy(doc.value?.party_type));

const status = computed(() => {
	if (!doc.value) return "";
	return doc.value.docstatus === 0 ? "Draft" : doc.value.onboarding_status || "Submitted";
});

const theme = computed<BadgeTheme>(() => STATUS_THEME[status.value] ?? "gray");

const timeline = computed(() => {
	const value = status.value;
	return [
		{ label: "Submitted", done: doc.value?.docstatus !== 0 },
		{
			label: "Under review",
			done: ["Approved", "Rejected"].includes(value) || value === "Pending Review",
		},
		{ label: "Decision", done: ["Approved", "Rejected"].includes(value) },
	];
});

const details = computed(() => {
	const d = doc.value;
	if (!d) return [];
	const primary = d.contacts.find((c) => c.is_primary_contact);
	const billing =
		d.contacts.find((c) => !c.is_primary_contact && c.is_billing_contact) ?? primary;
	return [
		["Applying as", d.party_type],
		["Type", d.onboarding_template],
		["Name", d.party_name],
		["Tax registration", d.tax_id],
		["Registration no", d.registration_number],
		["Primary contact", fullName(primary)],
		["Email", primary?.email_id],
		["Mobile", primary?.mobile_no],
		["Billing contact", fullName(billing)],
	];
});

const places = computed(() => {
	const d = doc.value;
	if (!d) return [];
	const label = (a: ApplicationAddress) =>
		a.is_primary_address
			? a.is_shipping_address
				? "Registered · deliveries"
				: "Registered"
			: a.is_shipping_address
			? "Delivery"
			: a.address_type;
	return [...d.addresses]
		.sort((a, b) => b.is_primary_address - a.is_primary_address)
		.map((a) => ({ label: label(a), text: oneLineAddress(a) }));
});
</script>

<template>
	<PageContainer
		:title="doc?.party_name || 'Application'"
		:subtitle="copy ? `${props.name} · applying as a ${copy.noun}` : props.name"
	>
		<template #actions>
			<Badge v-if="status" :theme="theme" variant="subtle" :label="status" size="lg" />
		</template>

		<div v-if="application.loading && !doc" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<div v-else-if="doc" class="space-y-6">
			<div v-if="doc.company_logo" class="flex items-center gap-3">
				<Avatar
					:image="doc.company_logo"
					:label="doc.party_name || 'Logo'"
					size="2xl"
					shape="square"
				/>
				<span class="text-p-sm text-ink-gray-5">Company logo</span>
			</div>

			<div
				v-if="doc.review_remarks"
				class="rounded-6 border p-4"
				:class="
					status === 'Approved'
						? 'border-outline-green-2 bg-surface-green-1'
						: 'border-outline-amber-2 bg-surface-amber-1'
				"
			>
				<p class="text-base font-medium text-ink-gray-8">
					{{ status === "Approved" ? "Approved" : "From our team" }}
				</p>
				<p class="mt-1 whitespace-pre-line text-p-base text-ink-gray-7">
					{{ doc.review_remarks }}
				</p>
				<Button
					v-if="doc.is_correction"
					class="mt-3"
					variant="solid"
					label="Fix and resubmit"
					icon-left="lucide-rotate-ccw"
					:route="{ name: 'ApplicationForm', query: { name: doc.name } }"
				/>
			</div>

			<div
				v-else-if="doc.can_edit"
				class="flex items-center justify-between gap-3 rounded-6 border p-4"
			>
				<p class="text-p-base text-ink-gray-7">
					This application is a draft and has not been sent to us yet.
				</p>
				<Button
					variant="solid"
					label="Continue"
					icon-left="lucide-pencil"
					:route="{ name: 'ApplicationForm', query: { name: doc.name } }"
				/>
			</div>

			<div
				v-if="doc.party"
				class="rounded-6 border border-outline-green-2 bg-surface-green-1 p-4"
			>
				<p class="text-base font-medium text-ink-gray-8">
					You are now a registered {{ copy?.noun }}
				</p>
				<p class="mt-1 text-p-sm text-ink-gray-7">{{ copy?.outcome }}</p>
			</div>

			<div class="flex items-center gap-2">
				<template v-for="(stage, index) in timeline" :key="stage.label">
					<div class="flex items-center gap-2">
						<span
							class="flex size-5 items-center justify-center rounded-full text-xs"
							:class="
								stage.done
									? 'bg-surface-gray-7 text-white'
									: 'border bg-surface-base text-ink-gray-5'
							"
						>
							{{ index + 1 }}
						</span>
						<span
							class="text-p-sm"
							:class="stage.done ? 'font-medium text-ink-gray-8' : 'text-ink-gray-5'"
						>
							{{ stage.label }}
						</span>
					</div>
					<div
						v-if="index < timeline.length - 1"
						class="h-px flex-1 bg-surface-gray-3"
					/>
				</template>
			</div>

			<dl class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-2">
				<div v-for="row in details" :key="row[0] as string">
					<dt class="text-xs uppercase tracking-wide text-ink-gray-5">{{ row[0] }}</dt>
					<dd class="text-p-base text-ink-gray-8">{{ row[1] || "—" }}</dd>
				</div>
			</dl>

			<div v-if="places.length">
				<h2 class="mb-3 text-base font-semibold text-ink-gray-8">Addresses</h2>
				<div class="divide-y rounded-6 border">
					<div
						v-for="(place, index) in places"
						:key="index"
						class="flex items-start justify-between gap-3 p-3"
					>
						<p class="min-w-0 text-p-base text-ink-gray-8">{{ place.text || "—" }}</p>
						<Badge theme="gray" variant="subtle" :label="place.label" />
					</div>
				</div>
			</div>

			<div v-if="doc.documents?.length">
				<h2 class="mb-3 text-base font-semibold text-ink-gray-8">Supporting documents</h2>
				<div class="divide-y rounded-6 border">
					<div
						v-for="item in doc.documents"
						:key="item.document_type"
						class="flex items-center justify-between gap-3 p-3"
					>
						<div class="min-w-0">
							<p class="truncate text-p-base text-ink-gray-8">
								{{ item.document_type }}
							</p>
							<p v-if="item.expiry_date" class="text-xs text-ink-gray-5">
								Expires {{ item.expiry_date }}
							</p>
						</div>
						<a
							v-if="item.attachment"
							:href="item.attachment"
							target="_blank"
							class="shrink-0 text-p-sm text-ink-gray-7 underline"
						>
							View
						</a>
						<Badge v-else theme="gray" variant="subtle" label="Not attached" />
					</div>
				</div>
			</div>

			<Button
				variant="subtle"
				label="Back to applications"
				:route="{ name: 'ApplicationList' }"
			/>
		</div>
	</PageContainer>
</template>
