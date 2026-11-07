<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	Avatar,
	Badge,
	Button,
	Checkbox,
	ErrorMessage,
	FileUploader,
	FormControl,
	Progress,
	Spinner,
	toast,
} from "frappe-ui";
import AddressFields from "@/components/AddressFields.vue";
import ApplicationSummary from "@/components/ApplicationSummary.vue";
import type { SummarySection } from "@/components/ApplicationSummary.vue";
import DownloadApplicationButton from "@/components/DownloadApplicationButton.vue";
import ContactFields from "@/components/ContactFields.vue";
import DocumentRequirementRow from "@/components/DocumentRequirementRow.vue";
import LinkSelect from "@/components/LinkSelect.vue";
import PageContainer from "@/components/PageContainer.vue";
import {
	blankAddress,
	blankContact,
	createApplicationResource,
	documentProblems,
	fetchProgress,
	localToday,
	normaliseTaxId,
	onboardingTypes,
	resubmitApplication,
	saveApplication,
	submitApplication,
	taxIdFormats,
	taxIdProblem,
	uploadEndpoint,
	uploadedAttachment,
} from "@/data/application";
import type {
	Application,
	ApplicationAddress,
	ApplicationContact,
	ApplicationProgress,
	OnboardingType,
	RequiredDocument,
	TaxIdFormat,
} from "@/data/application";
import { PARTY_COPY, PARTY_TYPES, partyCopy } from "@/data/parties";
import type { PartyType } from "@/data/parties";
import { usePortalStore } from "@/stores/portal";

const router = useRouter();
const route = useRoute();
const portal = usePortalStore();

const application = createApplicationResource();
const progress = ref<ApplicationProgress | null>(null);
const saving = ref(false);
const submitting = ref(false);
const loadError = ref<string | null>(null);

const form = reactive<Partial<Application>>({});
const contacts = ref<ApplicationContact[]>([]);
const addresses = ref<ApplicationAddress[]>([]);
const documents = ref<RequiredDocument[]>([]);

const isCorrection = computed(() => !!application.data?.is_correction);
const reviewRemarks = computed<string | null>(() => application.data?.review_remarks ?? null);
const isLocked = computed(() => application.data != null && !application.data.can_edit);

const openPartyTypes = computed(() => portal.openPartyTypes as PartyType[]);

const offeredPartyTypes = computed(() =>
	PARTY_TYPES.filter((p) => openPartyTypes.value.includes(p) || form.party_type === p)
);

const copy = computed(() => partyCopy(form.party_type));

const allTypes = computed(() => (onboardingTypes.data ?? []) as OnboardingType[]);
const typesForParty = computed(() =>
	allTypes.value.filter((t) => t.party_type === form.party_type)
);
const selectedType = computed<OnboardingType | null>(
	() => allTypes.value.find((t) => t.name === form.onboarding_template) ?? null
);

const isIndividual = computed(
	() => (selectedType.value?.entity_type ?? form.entity_type) === "Individual"
);

function choosePartyType(partyType: PartyType) {
	if (isCorrection.value || form.party_type === partyType) return;

	form.party_type = partyType;
	const options = typesForParty.value;
	form.onboarding_template = options.length === 1 ? options[0]!.name : null;

	shapeForParty();
}

const steps = computed(() => [
	{ key: "type", label: "Applying as" },
	{ key: "business", label: isIndividual.value ? "About you" : "Business" },
	{ key: "people", label: "Contacts & addresses" },
	{ key: "documents", label: "Documents" },
	{ key: "review", label: "Review" },
]);

const taxFormat = computed<TaxIdFormat | null>(
	() =>
		((taxIdFormats.data?.data ?? {}) as Record<string, TaxIdFormat>)[form.country ?? ""] ??
		null
);

const taxError = computed(() => taxIdProblem(form.tax_id, taxFormat.value));

const taxTouched = ref(false);

function tidyTaxId() {
	taxTouched.value = true;
	form.tax_id = normaliseTaxId(form.tax_id, taxFormat.value);
}

const stepIndex = ref(0);
const currentStep = computed(
	() => steps.value[Math.min(stepIndex.value, steps.value.length - 1)]!
);
const stepPercent = computed(() => Math.round((stepIndex.value / (steps.value.length - 1)) * 100));

const primaryContact = computed(() => contacts.value.find((c) => c.is_primary_contact) ?? null);
const billingContact = computed(
	() => contacts.value.find((c) => !c.is_primary_contact && c.is_billing_contact) ?? null
);

const billingAddress = computed(() => addresses.value.find((a) => a.is_primary_address) ?? null);
const deliveryAddresses = computed(() => addresses.value.filter((a) => !a.is_primary_address));
const deliveryAddress = computed(() => deliveryAddresses.value[0] ?? null);

function ensureShape() {
	if (!primaryContact.value) {
		const [first, ...rest] = (portal.user?.full_name ?? "").split(" ");
		contacts.value.unshift(
			blankContact({
				is_primary_contact: 1,
				is_billing_contact: billingContact.value ? 0 : 1,
				first_name: first || null,
				last_name: rest.join(" ") || null,
				email_id: portal.user?.email ?? null,
			})
		);
	}

	if (!billingAddress.value) {
		addresses.value.unshift(
			blankAddress({
				is_primary_address: 1,
				is_shipping_address: form.party_type === "Customer" ? 1 : 0,
			})
		);
	}
	billingAddress.value!.address_type = "Billing";

	const primaries = contacts.value.filter((c) => c.is_primary_contact);
	const billing = contacts.value.filter((c) => !c.is_primary_contact && c.is_billing_contact);
	contacts.value = [...primaries.slice(0, 1), ...billing.slice(0, 1)];
}

function shapeForParty() {
	ensureShape();
	if (billingAddress.value) billingAddress.value.is_shipping_address = 0;
	if (!copy.value?.asksForDelivery) {
		addresses.value = addresses.value.filter((a) => a.is_primary_address);
		return;
	}
	const kept = deliveryAddresses.value[0];
	addresses.value = addresses.value.filter((a) => a.is_primary_address || a === kept);
	if (!kept) {
		addresses.value.push(
			blankAddress({
				address_type: "Shipping",
				is_shipping_address: 1,
				country: billingAddress.value?.country ?? null,
			})
		);
	}
	deliveryAddress.value!.is_shipping_address = 1;
	deliveryAddress.value!.address_type = "Shipping";
}

function setSeparateBilling(on: boolean) {
	const primary = primaryContact.value;
	if (on && !billingContact.value) {
		if (primary) primary.is_billing_contact = 0;
		contacts.value.push(blankContact({ is_billing_contact: 1 }));
	} else if (!on) {
		contacts.value = contacts.value.filter(
			(c) => c.is_primary_contact || !c.is_billing_contact
		);
		if (primary) primary.is_billing_contact = 1;
	}
}

const billingIsPrimary = computed({
	get: () => !billingContact.value,
	set: (same: boolean) => setSeparateBilling(!same),
});

const ADDRESS_LINES = [
	"address_line1",
	"address_line2",
	"city",
	"state",
	"pincode",
	"country",
] as const;

function copyBillingToDelivery() {
	const from = billingAddress.value;
	const to = deliveryAddress.value;
	if (!from || !to) return;
	for (const field of ADDRESS_LINES) to[field] = from[field];
}

function hydrate(data: Application | null) {
	if (!data) return;
	Object.assign(form, data);
	contacts.value = (data.contacts ?? []).map((c) => ({ ...c }));
	addresses.value = (data.addresses ?? []).map((a) => ({ ...a }));
	documents.value = (data.documents ?? []).map((d) => ({ ...d }));
	if (data.party_type) shapeForParty();
	else ensureShape();
}

function partyTypeFromRoute(): PartyType | null {
	const wanted = String(route.query.as ?? "").toLowerCase();
	return (
		PARTY_TYPES.find((p) => p.toLowerCase() === wanted && openPartyTypes.value.includes(p)) ??
		null
	);
}

onMounted(async () => {
	taxIdFormats.fetch();
	try {
		await onboardingTypes.fetch();
		const name = (route.query.name as string) || null;
		const existing = (await application.fetch({ name })) as Application | null;

		if (existing) {
			hydrate(existing);
			if (!existing.can_edit) {
				router.replace({ name: "ApplicationDetail", params: { name: existing.name } });
				return;
			}
			if (!existing.party_type) {
				const wanted = partyTypeFromRoute();
				if (wanted) choosePartyType(wanted);
			}
			if (existing.is_correction) goToStep("review");
			await refreshProgress();
		} else {
			const only = openPartyTypes.value.length === 1 ? openPartyTypes.value[0]! : null;
			const wanted = partyTypeFromRoute() ?? only;
			if (wanted) choosePartyType(wanted);
			ensureShape();
		}
	} catch (error: any) {
		loadError.value =
			error?.messages?.[0] || error?.message || "Could not load the application.";
	}
});

async function refreshProgress() {
	if (!application.data?.name) return;
	progress.value = (await fetchProgress(application.data.name)) as ApplicationProgress;
}

function payload(): Partial<Application> {
	return {
		...form,
		contacts: contacts.value,
		addresses: addresses.value,
		documents: documents.value,
	};
}

async function save({ silent = false, refill = true } = {}) {
	if (isLocked.value) return;
	clearTimeout(documentSaveTimer);
	saving.value = true;
	try {
		const saved = (await saveApplication(payload(), application.data?.name)) as Application;
		application.data = saved;
		if (refill) hydrate(saved);
		await refreshProgress();
		if (!silent) toast.success("Progress saved");
		return saved;
	} catch (error: any) {
		toast.error(error?.messages?.[0] || error?.message || "Could not save");
		throw error;
	} finally {
		saving.value = false;
	}
}

const stepIssues = computed<string[]>(() => {
	const missing: string[] = [];
	const blank = (value: unknown) => !String(value ?? "").trim();
	const type = selectedType.value;

	switch (currentStep.value.key) {
		case "type":
			if (!form.party_type)
				missing.push("Choose whether you want to be a supplier or a customer");
			else if (blank(form.onboarding_template))
				missing.push(`What kind of ${copy.value?.noun} you are`);
			break;

		case "business":
			if (blank(form.party_name))
				missing.push(isIndividual.value ? "Your full name" : "Registered business name");
			if (type?.require_tax_id && blank(form.tax_id))
				missing.push(taxFormat.value?.label ?? "Tax registration number");
			if (taxError.value) missing.push(taxError.value);
			if (type?.require_registration_number && blank(form.registration_number))
				missing.push("Company registration number");
			break;

		case "people": {
			const primary = primaryContact.value;
			if (blank(primary?.first_name)) missing.push("Primary contact first name");
			if (blank(primary?.last_name)) missing.push("Primary contact last name");
			if (blank(primary?.email_id)) missing.push("Primary contact email address");
			if (blank(primary?.mobile_no)) missing.push("Primary contact mobile number");
			if (billingContact.value) {
				if (blank(billingContact.value.first_name))
					missing.push("Billing contact first name");
				if (blank(billingContact.value.email_id))
					missing.push("Billing contact email address");
			}
			addresses.value.forEach((address) => {
				const where = address.is_primary_address ? "Billing address" : "Delivery address";
				if (blank(address.address_line1)) missing.push(`${where}: address line 1`);
				if (blank(address.city)) missing.push(`${where}: city / town`);
				if (blank(address.country)) missing.push(`${where}: country`);
			});
			if (copy.value?.asksForDelivery && !deliveryAddress.value)
				missing.push("A delivery address");
			break;
		}

		case "documents": {
			const today = localToday();
			documents.value.forEach((row) =>
				documentProblems(row, today).forEach((problem) =>
					missing.push(`${row.document_type}: ${problem.toLowerCase()}`)
				)
			);
			break;
		}
	}

	return missing;
});

const canContinue = computed(() => stepIssues.value.length === 0);

async function next() {
	if (!canContinue.value) return;
	await save({ silent: true });
	if (stepIndex.value < steps.value.length - 1) stepIndex.value += 1;
}

function back() {
	if (stepIndex.value > 0) stepIndex.value -= 1;
}

function goToStep(key: SummarySection | "review") {
	const index = steps.value.findIndex((step) => step.key === key);
	if (index >= 0) stepIndex.value = index;
	window.scrollTo({ top: 0, behavior: "smooth" });
}

async function backToReview() {
	await save({ silent: true });
	goToStep("review");
}

function onLogoUploaded(response: unknown) {
	try {
		form.company_logo = uploadedAttachment(response).file_url;
		save({ silent: true });
	} catch (error: any) {
		toast.error(error?.message || "The upload did not go through.");
	}
}

function onUploadFailed(error: any) {
	const message = typeof error === "string" ? error : error?.messages?.[0] || error?.message;
	if (message) toast.error(message);
}

function removeLogo() {
	form.company_logo = null;
	save({ silent: true });
}

let documentSaveTimer: ReturnType<typeof setTimeout> | undefined;

function updateDocument(index: number, patch: Partial<RequiredDocument>) {
	documents.value[index] = { ...documents.value[index]!, ...patch };
	clearTimeout(documentSaveTimer);
	if ("attachment" in patch) {
		save({ silent: true });
		return;
	}
	documentSaveTimer = setTimeout(() => save({ silent: true, refill: false }), 1200);
}

onBeforeUnmount(() => clearTimeout(documentSaveTimer));

async function submit() {
	submitting.value = true;
	try {
		const correcting = isCorrection.value;
		await save({ silent: true });
		const name = application.data!.name;
		const submitted = (
			correcting ? await resubmitApplication(name, payload()) : await submitApplication(name)
		) as Application;
		toast.success(
			correcting ? "Application resubmitted for review" : "Application submitted for review"
		);
		await portal.session.reload();
		router.push({ name: "ApplicationDetail", params: { name: submitted.name } });
	} catch (error: any) {
		toast.error(error?.messages?.[0] || error?.message || "Could not submit");
	} finally {
		submitting.value = false;
	}
}

watch(
	() => form.onboarding_template,
	async (value, previous) => {
		if (!value || value === previous || previous === undefined || !application.data?.name)
			return;
		await save({ silent: true });
	}
);

const title = computed(() => {
	if (isCorrection.value) return "Correct your application";
	return copy.value ? `Become a ${copy.value.noun}` : "Apply to work with us";
});
</script>

<template>
	<PageContainer :title="title">
		<template #actions>
			<Badge v-if="saving" theme="gray" variant="subtle" label="Saving…" />
			<Button
				v-else-if="application.data"
				variant="subtle"
				label="Save draft"
				@click="save()"
			/>
		</template>

		<ErrorMessage v-if="loadError" :message="loadError" class="mb-4" />

		<div
			v-if="isCorrection"
			class="mb-6 rounded-8 border border-outline-amber-3 bg-surface-amber-1 p-4"
			role="status"
		>
			<div class="flex items-start gap-3">
				<i
					class="lucide-rotate-ccw mt-0.5 size-5 shrink-0 text-ink-amber-7"
					aria-hidden="true"
				/>
				<div class="min-w-0 flex-1">
					<p class="text-base font-semibold text-ink-gray-9">
						Our team asked for changes to your application
					</p>
					<blockquote
						v-if="reviewRemarks"
						class="mt-2 whitespace-pre-line rounded-6 border-l-[3px] border-outline-gray-7 bg-surface-base px-3 py-2 text-p-base text-ink-gray-8"
					>
						{{ reviewRemarks }}
					</blockquote>

					<p class="mt-3 text-p-sm font-semibold text-ink-gray-8">What to do next</p>
					<ol class="mt-1.5 grid gap-2 text-p-sm text-ink-gray-7 sm:grid-cols-3">
						<li class="flex items-start gap-2">
							<span class="correction-step">1</span>
							<span>Read the note from our team above.</span>
						</li>
						<li class="flex items-start gap-2">
							<span class="correction-step">2</span>
							<span>
								Tap <b>Edit</b> on the part the note is about and make the change.
								Everything else you entered is kept.
							</span>
						</li>
						<li class="flex items-start gap-2">
							<span class="correction-step">3</span>
							<span
								>Come back to <b>Review</b> and tap
								<b>Resubmit for review</b>.</span
							>
						</li>
					</ol>

					<Button
						v-if="currentStep.key !== 'review'"
						class="mt-3"
						variant="solid"
						icon-left="lucide-list-checks"
						label="Save and back to review"
						:loading="saving"
						@click="backToReview"
					/>
				</div>
			</div>
		</div>

		<div
			v-if="onboardingTypes.loading && !onboardingTypes.data"
			class="flex justify-center py-16"
		>
			<Spinner class="size-5" />
		</div>

		<div
			v-else-if="!offeredPartyTypes.length"
			class="rounded-6 border border-dashed py-16 text-center"
		>
			<p class="text-base font-medium text-ink-gray-7">
				We are not taking applications right now
			</p>
			<p class="mt-1 text-p-sm text-ink-gray-5">
				Please check back later, or contact our team.
			</p>
		</div>

		<div v-else class="space-y-6">
			<div>
				<div class="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
					<button
						v-for="(step, index) in steps"
						:key="step.key"
						class="rounded-4 px-2 py-1 text-sm transition"
						:class="
							index === stepIndex
								? 'bg-surface-gray-3 font-medium text-ink-gray-9'
								: index < stepIndex
								? 'text-ink-gray-7 hover:bg-surface-gray-2'
								: 'text-ink-gray-4'
						"
						:disabled="index > stepIndex && !isCorrection"
						@click="stepIndex = index"
					>
						{{ index + 1 }}. {{ step.label }}
					</button>
				</div>
				<Progress :value="stepPercent" size="sm" />
			</div>

			<section v-if="currentStep.key === 'type'" class="space-y-6">
				<div class="space-y-3">
					<p class="text-p-base text-ink-gray-6">
						<template v-if="isCorrection">
							You applied as a {{ copy?.noun }}. That cannot change on a correction.
						</template>
						<template v-else-if="offeredPartyTypes.length > 1">
							How would you like to work with us? One account can hold both — apply
							for the other later if you need to.
						</template>
						<template v-else>You are applying as a {{ copy?.noun }}.</template>
					</p>

					<div class="grid gap-3 sm:grid-cols-2">
						<button
							v-for="partyType in offeredPartyTypes"
							:key="partyType"
							type="button"
							class="group rounded-6 border p-5 text-left transition"
							:class="[
								form.party_type === partyType
									? 'border-outline-gray-4 bg-surface-gray-1 ring-1 ring-outline-gray-3'
									: 'bg-surface-base hover:border-outline-gray-3',
								isCorrection && form.party_type !== partyType ? 'opacity-50' : '',
							]"
							:disabled="isCorrection"
							:aria-pressed="form.party_type === partyType"
							@click="choosePartyType(partyType)"
						>
							<div class="flex items-center justify-between">
								<span
									class="flex size-9 items-center justify-center rounded-full bg-surface-gray-2 group-hover:bg-surface-gray-3"
								>
									<i
										:class="[
											PARTY_COPY[partyType].icon,
											'size-4 text-ink-gray-7',
										]"
									/>
								</span>
								<i
									v-if="form.party_type === partyType"
									class="lucide-circle-check-big size-4 text-ink-green-3"
								/>
							</div>
							<p class="mt-3 text-lg font-semibold text-ink-gray-9">
								{{ PARTY_COPY[partyType].headline }}
							</p>
							<p class="text-sm font-medium text-ink-gray-6">
								Become a {{ PARTY_COPY[partyType].noun }}
							</p>
							<p class="mt-2 text-p-sm text-ink-gray-6">
								{{ PARTY_COPY[partyType].pitch }}
							</p>
						</button>
					</div>
				</div>

				<div v-if="form.party_type" class="space-y-3">
					<h3 class="text-base font-semibold text-ink-gray-8">
						What kind of {{ copy?.noun }} are you?
					</h3>
					<p v-if="!typesForParty.length" class="text-p-sm text-ink-gray-5">
						No {{ copy?.noun }} types are set up yet. Please contact our team.
					</p>
					<div class="grid gap-3 sm:grid-cols-2">
						<button
							v-for="type in typesForParty"
							:key="type.name"
							type="button"
							class="rounded-6 border p-4 text-left transition hover:border-outline-gray-3"
							:class="
								form.onboarding_template === type.name
									? 'border-outline-gray-4 bg-surface-gray-1 ring-1 ring-outline-gray-3'
									: 'bg-surface-base'
							"
							:disabled="isCorrection"
							@click="form.onboarding_template = type.name"
						>
							<div class="flex items-center justify-between">
								<span class="text-base font-medium text-ink-gray-8">{{
									type.name
								}}</span>
								<i
									v-if="form.onboarding_template === type.name"
									class="lucide-circle-check-big size-4 text-ink-green-3"
								/>
							</div>
							<p v-if="type.description" class="mt-1 text-p-sm text-ink-gray-6">
								{{ type.description }}
							</p>
							<p class="mt-2 text-xs text-ink-gray-5">
								{{ type.entity_type }} · {{ type.documents.length }} supporting
								{{ type.documents.length === 1 ? "document" : "documents" }}
							</p>
						</button>
					</div>

					<div
						v-if="selectedType?.documents.length"
						class="rounded-6 border bg-surface-gray-1 p-4"
					>
						<p class="mb-2 text-sm font-medium text-ink-gray-7">
							You will need to upload
						</p>
						<ul class="space-y-1">
							<li
								v-for="doc in selectedType.documents"
								:key="doc.document_type"
								class="flex items-center gap-2 text-p-sm text-ink-gray-7"
							>
								<i class="lucide-paperclip size-3.5 text-ink-gray-5" />
								{{ doc.document_type }}
								<Badge
									v-if="doc.is_mandatory"
									theme="red"
									variant="subtle"
									label="Required"
								/>
							</li>
						</ul>
					</div>
				</div>
			</section>

			<section v-else-if="currentStep.key === 'business'" class="space-y-5">
				<div class="flex items-center gap-4">
					<Avatar
						:image="form.company_logo || undefined"
						:label="form.party_name || 'You'"
						size="3xl"
						:shape="isIndividual ? 'circle' : 'square'"
					/>
					<div class="space-y-1">
						<p class="text-base font-medium text-ink-gray-8">
							{{ isIndividual ? "Photo" : "Logo" }}
						</p>
						<p class="text-p-sm text-ink-gray-5">
							Optional. Shown on your {{ copy?.noun }} record once you are approved.
						</p>
						<div class="flex items-center gap-2 pt-1">
							<FileUploader
								v-if="application.data?.name"
								:upload-endpoint="
									uploadEndpoint(application.data.name, { purpose: 'logo' })
								"
								file-types=".png,.jpg,.jpeg,.webp,.gif"
								@success="onLogoUploaded"
								@failure="onUploadFailed"
							>
								<template
									#default="{ openFileSelector, uploading, progress: percent }"
								>
									<Button
										:loading="uploading"
										:label="
											uploading
												? `${percent}%`
												: form.company_logo
												? 'Replace'
												: 'Upload'
										"
										icon-left="lucide-image-up"
										@click="openFileSelector"
									/>
								</template>
							</FileUploader>
							<Button
								v-if="form.company_logo"
								variant="ghost"
								label="Remove"
								icon-left="lucide-trash-2"
								@click="removeLogo"
							/>
						</div>
					</div>
				</div>

				<div class="grid gap-4 sm:grid-cols-2">
					<FormControl
						v-model="form.party_name"
						:label="isIndividual ? 'Your full name' : 'Registered business name'"
						required
					/>
					<FormControl
						v-if="!isIndividual"
						v-model="form.website"
						label="Website"
						placeholder="https://"
					/>
					<LinkSelect
						v-model="form.country"
						doctype="Country"
						:label="isIndividual ? 'Country of residence' : 'Country of registration'"
					/>
					<div>
						<FormControl
							v-model="form.tax_id"
							:label="
								taxFormat?.label ??
								(isIndividual ? 'Personal tax number' : 'Tax registration number')
							"
							:placeholder="taxFormat ? `e.g. ${taxFormat.example}` : undefined"
							:required="!!selectedType?.require_tax_id"
							@blur="tidyTaxId"
						/>
						<p
							v-if="taxError && (taxTouched || stepIssues.length)"
							class="mt-1.5 flex items-start gap-1.5 text-p-xs text-ink-red-4"
							role="alert"
						>
							<i
								class="lucide-circle-alert mt-0.5 size-3.5 shrink-0"
								aria-hidden="true"
							/>
							{{ taxError }}
						</p>
						<p v-else-if="taxFormat" class="mt-1.5 text-p-xs text-ink-gray-5">
							{{ taxFormat.hint }}
						</p>
					</div>
					<FormControl
						v-if="!isIndividual || selectedType?.require_registration_number"
						v-model="form.registration_number"
						label="Company registration number"
						:required="!!selectedType?.require_registration_number"
					/>
				</div>
			</section>

			<section v-else-if="currentStep.key === 'people'" class="space-y-8">
				<div
					class="flex items-start gap-3 rounded-6 border border-outline-gray-2 bg-surface-gray-1 p-3"
					role="note"
				>
					<i
						class="lucide-info mt-0.5 size-4 shrink-0 text-ink-gray-6"
						aria-hidden="true"
					/>
					<p class="text-p-sm text-ink-gray-7">
						We only need the essentials to get you started:
						<b>one primary contact</b>, <b>one billing contact</b>,
						<b>one billing address</b
						><template v-if="copy?.asksForDelivery">
							and <b>one delivery address</b></template
						>. Once you are approved you can add more people and addresses any time
						from <b>Settings → Profile</b>.
					</p>
				</div>

				<div v-if="primaryContact" class="space-y-3">
					<div>
						<h3 class="text-base font-semibold text-ink-gray-8">Primary contact</h3>
						<p class="mt-0.5 text-p-sm text-ink-gray-5">
							{{ copy?.primaryContactHint }}
						</p>
					</div>
					<ContactFields :model-value="primaryContact" full />
				</div>

				<div class="space-y-3">
					<div>
						<h3 class="text-base font-semibold text-ink-gray-8">Billing contact</h3>
						<p class="mt-0.5 text-p-sm text-ink-gray-5">
							{{ copy?.billingContactHint }}
						</p>
					</div>
					<label
						class="flex cursor-pointer items-start gap-3 rounded-6 border border-outline-gray-2 p-3"
					>
						<Checkbox v-model="billingIsPrimary" />
						<span>
							<span class="block text-base font-medium text-ink-gray-8">
								Same person as the primary contact
							</span>
							<span class="mt-0.5 block text-p-sm text-ink-gray-6">
								Untick if invoices and statements should go to someone else, such
								as your accounts team.
							</span>
						</span>
					</label>
					<ContactFields v-if="billingContact" :model-value="billingContact" />
				</div>

				<div v-if="billingAddress" class="space-y-3">
					<div>
						<h3 class="text-base font-semibold text-ink-gray-8">
							{{ isIndividual ? "Your billing address" : "Billing address" }}
						</h3>
						<p class="mt-0.5 text-p-sm text-ink-gray-5">
							{{ copy?.billingAddressHint }}
						</p>
					</div>
					<AddressFields :model-value="billingAddress" />
				</div>

				<div v-if="copy?.asksForDelivery && deliveryAddress" class="space-y-3">
					<div class="flex flex-wrap items-end justify-between gap-2">
						<div>
							<h3 class="text-base font-semibold text-ink-gray-8">
								Delivery address
								<span class="text-ink-red-4" aria-hidden="true">*</span>
							</h3>
							<p class="mt-0.5 text-p-sm text-ink-gray-5">
								{{ copy.deliveryAddressHint }}
							</p>
						</div>
						<Button
							variant="subtle"
							icon-left="lucide-copy"
							label="Same as billing address"
							@click="copyBillingToDelivery"
						/>
					</div>
					<div class="rounded-6 border border-outline-gray-2 p-4">
						<AddressFields :model-value="deliveryAddress" />
					</div>
					<p class="flex items-start gap-1.5 text-p-sm text-ink-gray-6">
						<i class="lucide-info mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
						Deliver to more than one place? Add your other branches or sites after you
						are approved, from Settings → Profile.
					</p>
				</div>
			</section>

			<section v-else-if="currentStep.key === 'documents'" class="space-y-3">
				<div
					v-if="!application.data?.name"
					class="rounded-6 border bg-surface-amber-1 p-4"
				>
					<p class="text-p-base text-ink-gray-7">
						Save your details first — uploads attach to your saved application.
					</p>
				</div>

				<template v-else>
					<p v-if="!documents.length" class="text-p-base text-ink-gray-6">
						{{ form.onboarding_template }} needs no supporting documents.
					</p>
					<DocumentRequirementRow
						v-for="(doc, index) in documents"
						:key="doc.document_type"
						:document="doc"
						:docname="application.data.name"
						@update="updateDocument(index, $event)"
					/>
				</template>
			</section>

			<section v-else class="space-y-4">
				<div
					v-if="progress && !progress.can_submit"
					class="rounded-6 border border-outline-amber-2 bg-surface-amber-1 p-4"
				>
					<p class="mb-2 text-base font-medium text-ink-gray-8">Still outstanding</p>
					<ul class="list-inside list-disc space-y-1 text-p-sm text-ink-gray-7">
						<li v-for="item in progress.missing_details" :key="item">{{ item }}</li>
						<li v-for="item in progress.missing_documents" :key="item">
							{{ item }}
						</li>
					</ul>
				</div>

				<div
					v-else-if="progress"
					class="rounded-6 border border-outline-green-2 bg-surface-green-1 p-4"
				>
					<p class="text-base font-medium text-ink-gray-8">
						Everything we need is here.
					</p>
					<p class="mt-1 text-p-sm text-ink-gray-7">
						Once submitted your application is locked while our team reviews it.
					</p>
				</div>

				<div class="flex flex-wrap items-center justify-between gap-3">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">Check your details</h2>
						<p class="text-p-sm text-ink-gray-6">
							This is everything you entered. Tap Edit on any part to change it.
						</p>
					</div>
					<DownloadApplicationButton
						v-if="application.data?.name"
						:name="application.data.name"
						:before-download="() => save({ silent: true })"
					/>
				</div>

				<ApplicationSummary
					:application="payload()"
					:individual="isIndividual"
					:lock-type="isCorrection"
					editable
					@edit="goToStep"
				/>

				<p v-if="progress" class="text-p-sm text-ink-gray-6">
					{{ progress.documents_attached }} of {{ progress.documents_required }} required
					documents attached.
				</p>
			</section>

			<div
				v-if="stepIssues.length && currentStep.key !== 'review'"
				class="rounded-6 border border-outline-amber-2 bg-surface-amber-1 p-3"
			>
				<p class="flex items-center gap-2 text-p-sm font-medium text-ink-gray-8">
					<i class="lucide-circle-alert size-4 shrink-0 text-ink-amber-7" />
					{{
						stepIssues.length === 1
							? "One more thing before you continue"
							: `${stepIssues.length} things before you continue`
					}}
				</p>
				<ul class="ml-6 mt-1 list-disc text-p-sm text-ink-gray-7">
					<li v-for="item in stepIssues" :key="item">{{ item }}</li>
				</ul>
			</div>

			<div class="flex items-center justify-between border-t pt-4">
				<Button
					v-if="stepIndex > 0"
					variant="ghost"
					label="Back"
					icon-left="lucide-arrow-left"
					@click="back"
				/>
				<span v-else />

				<div class="flex items-center gap-2">
					<Button
						v-if="isCorrection && currentStep.key !== 'review'"
						variant="outline"
						label="Back to review"
						icon-left="lucide-list-checks"
						:loading="saving"
						@click="backToReview"
					/>
					<Button
						v-if="currentStep.key !== 'review'"
						variant="solid"
						label="Continue"
						icon-right="lucide-arrow-right"
						:loading="saving"
						:disabled="!canContinue"
						@click="next"
					/>
					<Button
						v-else
						variant="solid"
						theme="green"
						:label="isCorrection ? 'Resubmit for review' : 'Submit application'"
						:loading="submitting"
						:disabled="!progress?.can_submit"
						@click="submit"
					/>
				</div>
			</div>
		</div>
	</PageContainer>
</template>

<style scoped>
.correction-step {
	display: grid;
	flex-shrink: 0;
	place-items: center;
	width: 1.25rem;
	height: 1.25rem;
	border-radius: 9999px;
	background-color: var(--surface-gray-10);
	color: var(--ink-base);
	font-size: 0.6875rem;
	font-weight: 700;
}
</style>
