<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
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
import ContactFields from "@/components/ContactFields.vue";
import DocumentRequirementRow from "@/components/DocumentRequirementRow.vue";
import LinkSelect from "@/components/LinkSelect.vue";
import PageContainer from "@/components/PageContainer.vue";
import {
	attachmentUploadUrl,
	blankAddress,
	blankContact,
	createApplicationResource,
	fetchProgress,
	fullName,
	oneLineAddress,
	onboardingTypes,
	resubmitApplication,
	saveApplication,
	submitApplication,
} from "@/data/application";
import type {
	Application,
	ApplicationAddress,
	ApplicationContact,
	ApplicationProgress,
	OnboardingType,
	RequiredDocument,
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

const asksForBank = computed(
	() =>
		form.party_type === "Supplier" || !!selectedType.value?.require_bank_details || !!form.bank
);

const steps = computed(() => [
	{ key: "type", label: "Applying as" },
	{ key: "business", label: isIndividual.value ? "About you" : "Business" },
	{ key: "people", label: "Contacts & addresses" },
	...(asksForBank.value ? [{ key: "bank", label: "Bank details" }] : []),
	{ key: "documents", label: "Documents" },
	{ key: "review", label: "Review" },
]);

const stepIndex = ref(0);
const currentStep = computed(
	() => steps.value[Math.min(stepIndex.value, steps.value.length - 1)]!
);
const stepPercent = computed(() => Math.round((stepIndex.value / (steps.value.length - 1)) * 100));

const primaryContact = computed(() => contacts.value.find((c) => c.is_primary_contact) ?? null);
const billingContact = computed(
	() => contacts.value.find((c) => !c.is_primary_contact && c.is_billing_contact) ?? null
);

const registeredAddress = computed(
	() => addresses.value.find((a) => a.is_primary_address) ?? null
);
const extraAddresses = computed(() => addresses.value.filter((a) => !a.is_primary_address));

const EXTRA_ADDRESS_TYPES = ["Warehouse", "Office", "Plant", "Shop"];

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

	if (!registeredAddress.value) {
		addresses.value.unshift(
			blankAddress({
				is_primary_address: 1,
				is_shipping_address: form.party_type === "Customer" ? 1 : 0,
			})
		);
	}
}

function shapeForParty() {
	ensureShape();
	const delivers = !!copy.value?.asksForDelivery;

	for (const address of extraAddresses.value) {
		address.is_shipping_address = delivers ? 1 : 0;
		address.address_type = delivers
			? "Shipping"
			: EXTRA_ADDRESS_TYPES.includes(address.address_type)
			? address.address_type
			: "Warehouse";
	}
	if (!delivers && registeredAddress.value) registeredAddress.value.is_shipping_address = 0;
	if (delivers && registeredAddress.value && !extraAddresses.value.length)
		registeredAddress.value.is_shipping_address = 1;
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

function addExtraAddress() {
	const delivers = !!copy.value?.asksForDelivery;
	addresses.value.push(
		blankAddress({
			address_type: copy.value?.extraAddressType ?? "Other",
			is_shipping_address: delivers ? 1 : 0,
			country: registeredAddress.value?.country ?? null,
		})
	);
}

function removeAddress(address: ApplicationAddress) {
	addresses.value = addresses.value.filter((a) => a !== address);
	if (
		copy.value?.asksForDelivery &&
		!addresses.value.some((a) => a.is_shipping_address) &&
		registeredAddress.value
	)
		registeredAddress.value.is_shipping_address = 1;
}

const deliversToRegistered = computed({
	get: () => !!registeredAddress.value?.is_shipping_address,
	set: (value: boolean) => {
		if (registeredAddress.value) registeredAddress.value.is_shipping_address = value ? 1 : 0;
		if (!value && !extraAddresses.value.length) addExtraAddress();
	},
});

function hydrate(data: Application | null) {
	if (!data) return;
	Object.assign(form, data);
	contacts.value = (data.contacts ?? []).map((c) => ({ ...c }));
	addresses.value = (data.addresses ?? []).map((a) => ({ ...a }));
	documents.value = (data.documents ?? []).map((d) => ({ ...d }));
	ensureShape();
}

function partyTypeFromRoute(): PartyType | null {
	const wanted = String(route.query.as ?? "").toLowerCase();
	return (
		PARTY_TYPES.find((p) => p.toLowerCase() === wanted && openPartyTypes.value.includes(p)) ??
		null
	);
}

onMounted(async () => {
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

async function save({ silent = false } = {}) {
	if (isLocked.value) return;
	saving.value = true;
	try {
		const saved = (await saveApplication(payload(), application.data?.name)) as Application;
		application.data = saved;
		hydrate(saved);
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
				missing.push("Tax registration number");
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
				const where = address.is_primary_address
					? "Registered address"
					: `${address.address_type} address`;
				if (blank(address.address_line1)) missing.push(`${where}: address line 1`);
				if (blank(address.city)) missing.push(`${where}: city / town`);
				if (blank(address.country)) missing.push(`${where}: country`);
			});
			if (
				form.party_type === "Customer" &&
				type?.require_shipping_address &&
				!addresses.value.some((a) => a.is_shipping_address)
			)
				missing.push("Somewhere we deliver to");
			break;
		}

		case "bank":
			if (type?.require_bank_details) {
				if (blank(form.bank)) missing.push("Bank");
				if (blank(form.bank_account_no)) missing.push("Account number");
			}
			break;

		case "documents":
			documents.value
				.filter((row) => row.is_mandatory && !row.attachment)
				.forEach((row) => missing.push(row.document_type));
			break;
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

function onLogoUploaded(file: { file_url: string }) {
	form.company_logo = file.file_url;
	save({ silent: true });
}

function removeLogo() {
	form.company_logo = null;
	save({ silent: true });
}

function updateDocument(index: number, patch: Partial<RequiredDocument>) {
	documents.value[index] = { ...documents.value[index]!, ...patch };
	save({ silent: true });
}

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

const reviewRows = computed(() => {
	const rows: [string, string | null | undefined][] = [
		["Applying as", form.party_type],
		["Type", form.onboarding_template],
		[isIndividual.value ? "Name" : "Business name", form.party_name],
		["Tax registration", form.tax_id],
		["Registration no", form.registration_number],
		["Primary contact", fullName(primaryContact.value)],
		["Email", primaryContact.value?.email_id],
		["Mobile", primaryContact.value?.mobile_no],
		[
			"Billing contact",
			billingContact.value ? fullName(billingContact.value) : fullName(primaryContact.value),
		],
		["Registered address", oneLineAddress(registeredAddress.value)],
	];
	if (copy.value?.asksForDelivery) {
		const delivery = addresses.value.filter((a) => a.is_shipping_address).map(oneLineAddress);
		rows.push(["Deliver to", delivery.join(" · ")]);
	}
	return rows;
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
			v-if="isCorrection && reviewRemarks"
			class="mb-6 rounded-6 border border-outline-amber-2 bg-surface-amber-1 p-4"
		>
			<div class="flex items-start gap-2">
				<i class="lucide-rotate-ccw mt-0.5 size-4 shrink-0 text-ink-amber-7" />
				<div>
					<p class="text-base font-medium text-ink-gray-8">Sent back for correction</p>
					<p class="mt-1 whitespace-pre-line text-p-base text-ink-gray-7">
						{{ reviewRemarks }}
					</p>
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
						:disabled="index > stepIndex"
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
								:doctype="'Party Onboarding Request'"
								:docname="application.data.name"
								:upload-endpoint="attachmentUploadUrl()"
								file-types="image/*"
								@success="onLogoUploaded"
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
					<FormControl
						v-model="form.tax_id"
						:label="isIndividual ? 'Personal tax number' : 'Tax registration number'"
						:required="!!selectedType?.require_tax_id"
					/>
					<FormControl
						v-if="!isIndividual || selectedType?.require_registration_number"
						v-model="form.registration_number"
						label="Company registration number"
						:required="!!selectedType?.require_registration_number"
					/>
					<LinkSelect
						v-model="form.country"
						doctype="Country"
						:label="isIndividual ? 'Country of residence' : 'Country of registration'"
					/>
				</div>
			</section>

			<section v-else-if="currentStep.key === 'people'" class="space-y-8">
				<div class="space-y-4">
					<div v-if="primaryContact">
						<h3 class="mb-1 text-base font-semibold text-ink-gray-8">
							Primary contact
						</h3>
						<p class="mb-3 text-p-sm text-ink-gray-5">
							{{ copy?.primaryContactHint }}
						</p>
						<ContactFields :model-value="primaryContact" full />
					</div>

					<div class="rounded-6 border bg-surface-gray-1 p-4">
						<label class="flex cursor-pointer items-start gap-3">
							<Checkbox
								:model-value="!!billingContact"
								@update:model-value="setSeparateBilling(!!$event)"
							/>
							<span>
								<span class="block text-base font-medium text-ink-gray-8"
									>Add a billing contact</span
								>
								<span class="mt-0.5 block text-p-sm text-ink-gray-6">{{
									copy?.billingContactHint
								}}</span>
							</span>
						</label>

						<div v-if="billingContact" class="mt-4">
							<ContactFields :model-value="billingContact" />
						</div>

						<p v-else class="mt-3 flex items-start gap-2 text-p-sm text-ink-gray-5">
							<i class="lucide-info mt-0.5 size-4 shrink-0" />
							<span>
								Without one, billing goes to
								<span class="font-medium text-ink-gray-7">{{
									fullName(primaryContact) || "your primary contact"
								}}</span
								>, your primary contact.
							</span>
						</p>
					</div>
				</div>

				<div class="space-y-4">
					<div v-if="registeredAddress">
						<h3 class="mb-1 text-base font-semibold text-ink-gray-8">
							{{ isIndividual ? "Your address" : "Registered address" }}
						</h3>
						<p class="mb-3 text-p-sm text-ink-gray-5">
							{{ copy?.registeredAddressHint }}
						</p>
						<AddressFields :model-value="registeredAddress" />

						<label
							v-if="copy?.asksForDelivery"
							class="mt-4 flex cursor-pointer items-start gap-3 rounded-6 border bg-surface-gray-1 p-3"
						>
							<Checkbox v-model="deliversToRegistered" />
							<span>
								<span class="block text-base font-medium text-ink-gray-8"
									>We take deliveries here too</span
								>
								<span class="mt-0.5 block text-p-sm text-ink-gray-6">
									Untick if goods should always go somewhere else.
								</span>
							</span>
						</label>
					</div>

					<div
						v-for="(address, index) in extraAddresses"
						:key="index"
						class="rounded-6 border p-4"
					>
						<div class="mb-3 flex items-center justify-between gap-2">
							<p
								class="flex items-center gap-2 text-base font-medium text-ink-gray-8"
							>
								<i
									:class="[
										address.is_shipping_address
											? 'lucide-package-check'
											: 'lucide-warehouse',
										'size-4 text-ink-gray-5',
									]"
								/>
								{{
									address.is_shipping_address
										? "Delivery address"
										: `${address.address_type} address`
								}}
								{{ extraAddresses.length > 1 ? index + 1 : "" }}
							</p>
							<Button
								variant="ghost"
								icon-left="lucide-trash-2"
								label="Remove"
								@click="removeAddress(address)"
							/>
						</div>
						<AddressFields
							:model-value="address"
							:type-options="
								address.is_shipping_address ? undefined : EXTRA_ADDRESS_TYPES
							"
						/>
					</div>

					<button
						type="button"
						class="flex w-full items-center gap-3 rounded-6 border border-dashed p-4 text-left transition hover:border-outline-gray-3 hover:bg-surface-gray-1"
						@click="addExtraAddress"
					>
						<i class="lucide-plus size-4 text-ink-gray-6" />
						<span>
							<span class="block text-base font-medium text-ink-gray-8">{{
								copy?.extraAddressLabel
							}}</span>
							<span class="block text-p-sm text-ink-gray-5">{{
								copy?.extraAddressHint
							}}</span>
						</span>
					</button>
				</div>
			</section>

			<section v-else-if="currentStep.key === 'bank'" class="space-y-3">
				<p class="text-p-sm text-ink-gray-5">
					{{ copy?.bankHint }}
					<template v-if="!selectedType?.require_bank_details">
						Optional for {{ form.onboarding_template }}, but it saves time later.
					</template>
				</p>
				<div class="grid gap-4 sm:grid-cols-2">
					<LinkSelect
						v-model="form.bank"
						doctype="Bank"
						label="Bank"
						:required="!!selectedType?.require_bank_details"
					/>
					<FormControl
						v-model="form.bank_account_no"
						label="Account number"
						:required="!!selectedType?.require_bank_details"
					/>
					<FormControl v-model="form.account_holder_name" label="Account holder name" />
					<FormControl v-model="form.branch_code" label="Branch code" />
					<FormControl v-model="form.iban" label="IBAN" />
					<FormControl v-model="form.swift_number" label="SWIFT / BIC" />
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
							{{ item }} (document)
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

				<div v-if="form.company_logo" class="flex items-center gap-3">
					<Avatar
						:image="form.company_logo"
						:label="form.party_name || 'Logo'"
						size="2xl"
						:shape="isIndividual ? 'circle' : 'square'"
					/>
					<span class="text-p-sm text-ink-gray-5">{{
						isIndividual ? "Photo" : "Logo"
					}}</span>
				</div>

				<dl class="grid gap-x-6 gap-y-3 rounded-6 border p-4 sm:grid-cols-2">
					<div v-for="row in reviewRows" :key="row[0]">
						<dt class="text-xs uppercase tracking-wide text-ink-gray-5">
							{{ row[0] }}
						</dt>
						<dd class="text-p-base text-ink-gray-8">{{ row[1] || "—" }}</dd>
					</div>
				</dl>

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
