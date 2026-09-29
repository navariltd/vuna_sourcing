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
import { LOOKS } from "@/data/accents";

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

type StepState = "done" | "current" | "attention" | "failed" | "upcoming";

interface Stage {
	step: number;
	title: string;
	message: string;
	icon: string;
	labels: [string, string, string];
	states: [StepState, StepState, StepState];
}

const STAGES: Record<string, Stage> = {
	Draft: {
		step: 1,
		title: "Finish and send your application",
		message:
			"Your application is saved as a draft and has not reached us yet. Complete any missing details, attach the documents, and send it.",
		icon: "lucide-pencil-line",
		labels: ["Send application", "Under review", "Decision"],
		states: ["current", "upcoming", "upcoming"],
	},
	"Pending Review": {
		step: 2,
		title: "Under review",
		message:
			"We have received your application and our team is checking your details and documents.",
		icon: "lucide-hourglass",
		labels: ["Submitted", "Under review", "Decision"],
		states: ["done", "current", "upcoming"],
	},
	"Returned for Correction": {
		step: 2,
		title: "Changes requested",
		message:
			"Our team reviewed your application and needs a few changes before it can go further. Read the note below, fix what it asks for, and resubmit. It then goes back into review.",
		icon: "lucide-rotate-ccw",
		labels: ["Submitted", "Changes requested", "Decision"],
		states: ["done", "attention", "upcoming"],
	},
	Approved: {
		step: 3,
		title: "Approved",
		message: "Your application has been approved. Your account is set up and ready to use.",
		icon: "lucide-badge-check",
		labels: ["Submitted", "Reviewed", "Approved"],
		states: ["done", "done", "done"],
	},
	Rejected: {
		step: 3,
		title: "Not approved",
		message:
			"We are not able to take your application forward at this time. Any note from our team is shown below. You can contact us if you have questions.",
		icon: "lucide-circle-x",
		labels: ["Submitted", "Reviewed", "Not approved"],
		states: ["done", "done", "failed"],
	},
};

const STEP_HINTS: [string, string, string] = [
	"Your details and documents",
	"Our team checks everything",
	"We let you know the outcome",
];

const STEP_DOT: Record<StepState, string> = {
	done: "bg-surface-gray-7 text-white",
	current: "bg-surface-gray-9 text-white ring-4 ring-outline-gray-2",
	attention: "bg-surface-gray-9 text-white ring-4 ring-outline-gray-2",
	failed: "bg-surface-gray-7 text-white",
	upcoming: "border border-outline-gray-3 bg-surface-base text-ink-gray-5",
};

const stage = computed<Stage | null>(() => STAGES[status.value] ?? null);

const steps = computed(() => {
	const current = stage.value;
	if (!current) return [];
	return current.labels.map((label, index) => ({
		label,
		hint: STEP_HINTS[index],
		state: current.states[index] as StepState,
	}));
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
	<PageContainer :look="LOOKS.application" :title="doc?.party_name || 'Application'">
		<template #actions>
			<Badge v-if="status" :theme="theme" variant="subtle" :label="status" size="lg" />
		</template>

		<div v-if="application.loading && !doc" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<div v-else-if="doc" class="space-y-6">
			<section v-if="stage" class="rounded-6 border p-4">
				<div class="flex items-start gap-3">
					<i :class="[stage.icon, 'mt-0.5 size-5 shrink-0 text-ink-gray-6']" />
					<div class="min-w-0 flex-1">
						<p class="text-xs uppercase tracking-wide text-ink-gray-5">
							Step {{ stage.step }} of 3
						</p>
						<p class="mt-0.5 text-base font-semibold text-ink-gray-9">
							{{ stage.title }}
						</p>
						<p class="mt-1 text-p-base text-ink-gray-7">{{ stage.message }}</p>
						<Button
							v-if="doc.can_edit && !doc.is_correction"
							class="mt-3"
							variant="solid"
							label="Continue"
							icon-left="lucide-pencil"
							:route="{ name: 'ApplicationForm', query: { name: doc.name } }"
						/>
					</div>
				</div>

				<ol class="mt-4 grid gap-3 sm:grid-cols-3">
					<li
						v-for="(item, index) in steps"
						:key="index"
						class="flex items-start gap-2.5"
					>
						<span
							class="grid size-6 shrink-0 place-items-center rounded-full text-xs font-medium"
							:class="STEP_DOT[item.state]"
						>
							<i v-if="item.state === 'done'" class="lucide-check size-3.5" />
							<i v-else-if="item.state === 'failed'" class="lucide-x size-3.5" />
							<template v-else>{{ index + 1 }}</template>
						</span>
						<div class="min-w-0">
							<p
								class="text-p-sm"
								:class="
									item.state === 'upcoming'
										? 'text-ink-gray-5'
										: 'font-medium text-ink-gray-8'
								"
							>
								{{ item.label }}
								<span
									v-if="item.state === 'current' || item.state === 'attention'"
									class="ml-1 text-xs font-normal text-ink-gray-5"
								>
									· you are here
								</span>
							</p>
							<p class="text-xs text-ink-gray-5">{{ item.hint }}</p>
						</div>
					</li>
				</ol>
			</section>

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
				v-if="doc.party"
				class="rounded-6 border border-outline-green-2 bg-surface-green-1 p-4"
			>
				<p class="text-base font-medium text-ink-gray-8">
					You are now a registered {{ copy?.noun }}
				</p>
				<p class="mt-1 text-p-sm text-ink-gray-7">{{ copy?.outcome }}</p>
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
