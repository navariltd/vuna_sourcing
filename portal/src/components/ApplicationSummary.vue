<script setup lang="ts">
import { computed } from "vue";
import { Avatar, Badge, Button } from "frappe-ui";
import { fullName } from "@/data/application";
import type { Application, ApplicationAddress, ApplicationContact } from "@/data/application";

export type SummarySection = "type" | "business" | "people" | "bank" | "documents";

const props = defineProps<{
	application: Partial<Application>;
	individual?: boolean;
	showBank?: boolean;
	editable?: boolean;
	lockType?: boolean;
}>();

const emit = defineEmits<{ (e: "edit", section: SummarySection): void }>();

const contacts = computed(() =>
	[...(props.application.contacts ?? [])].sort(
		(a, b) => b.is_primary_contact - a.is_primary_contact
	)
);

const addresses = computed(() =>
	[...(props.application.addresses ?? [])].sort(
		(a, b) => b.is_primary_address - a.is_primary_address
	)
);

const documents = computed(() => props.application.documents ?? []);

const business = computed(() => [
	[props.individual ? "Full name" : "Business name", props.application.party_name],
	[props.individual ? "Personal tax number" : "Tax registration", props.application.tax_id],
	["Registration no", props.application.registration_number],
	[
		props.individual ? "Country of residence" : "Country of registration",
		props.application.country,
	],
	...(props.individual ? [] : [["Website", props.application.website]]),
]);

const bank = computed(() => [
	["Bank", props.application.bank],
	["Account number", props.application.bank_account_no],
	["Account holder", props.application.account_holder_name],
	["Branch code", props.application.branch_code],
	["IBAN", props.application.iban],
	["SWIFT / BIC", props.application.swift_number],
]);

function contactRole(contact: ApplicationContact) {
	const roles = [
		contact.is_primary_contact ? "Primary" : null,
		contact.is_billing_contact ? "Billing" : null,
	].filter(Boolean);
	return roles.join(" · ") || "Contact";
}

function addressRole(address: ApplicationAddress) {
	if (address.is_primary_address)
		return address.is_shipping_address ? "Registered · deliveries" : "Registered";
	return address.is_shipping_address ? "Delivery" : address.address_type;
}

function fullAddress(address: ApplicationAddress) {
	return [
		address.address_line1,
		address.address_line2,
		address.city,
		address.state,
		address.pincode,
		address.country,
	]
		.filter(Boolean)
		.join(", ");
}
</script>

<template>
	<div class="flex flex-col gap-4">
		<section class="summary-card">
			<header class="summary-head">
				<h3>Applying as</h3>
				<span v-if="editable && lockType" class="text-p-xs text-ink-gray-5">
					Cannot change on a correction
				</span>
				<Button
					v-else-if="editable"
					size="sm"
					variant="subtle"
					icon-left="lucide-pencil"
					label="Edit"
					@click="emit('edit', 'type')"
				/>
			</header>
			<dl class="summary-grid">
				<div>
					<dt>Party</dt>
					<dd>{{ application.party_type || "—" }}</dd>
				</div>
				<div>
					<dt>Type</dt>
					<dd>{{ application.onboarding_template || "—" }}</dd>
				</div>
			</dl>
		</section>

		<section class="summary-card">
			<header class="summary-head">
				<h3>{{ individual ? "About you" : "Business" }}</h3>
				<Button
					v-if="editable"
					size="sm"
					variant="subtle"
					icon-left="lucide-pencil"
					label="Edit"
					@click="emit('edit', 'business')"
				/>
			</header>
			<div v-if="application.company_logo" class="mb-3 flex items-center gap-3">
				<Avatar
					:image="application.company_logo"
					:label="application.party_name || 'Logo'"
					size="xl"
					:shape="individual ? 'circle' : 'square'"
				/>
				<span class="text-p-sm text-ink-gray-5">{{ individual ? "Photo" : "Logo" }}</span>
			</div>
			<dl class="summary-grid">
				<div v-for="[label, value] in business" :key="label as string">
					<dt>{{ label }}</dt>
					<dd>{{ value || "—" }}</dd>
				</div>
			</dl>
		</section>

		<section class="summary-card">
			<header class="summary-head">
				<h3>Contacts & addresses</h3>
				<Button
					v-if="editable"
					size="sm"
					variant="subtle"
					icon-left="lucide-pencil"
					label="Edit"
					@click="emit('edit', 'people')"
				/>
			</header>
			<div class="flex flex-col gap-2">
				<div
					v-for="(contact, index) in contacts"
					:key="`contact-${index}`"
					class="rounded-6 bg-surface-gray-1 p-3"
				>
					<div class="flex flex-wrap items-center justify-between gap-2">
						<p class="text-base font-medium text-ink-gray-9">
							{{ fullName(contact) || "—" }}
							<span v-if="contact.designation" class="font-normal text-ink-gray-5">
								· {{ contact.designation }}
							</span>
						</p>
						<Badge theme="gray" variant="solid" :label="contactRole(contact)" />
					</div>
					<p class="mt-1 text-p-sm text-ink-gray-7">
						{{ contact.email_id || "No email" }} ·
						{{ contact.mobile_no || "No mobile" }}
					</p>
				</div>
				<div
					v-for="(address, index) in addresses"
					:key="`address-${index}`"
					class="flex items-start justify-between gap-3 rounded-6 bg-surface-gray-1 p-3"
				>
					<p class="min-w-0 text-p-sm text-ink-gray-8">
						{{ fullAddress(address) || "—" }}
					</p>
					<Badge
						class="shrink-0"
						theme="gray"
						variant="solid"
						:label="addressRole(address)"
					/>
				</div>
				<p v-if="!contacts.length && !addresses.length" class="text-p-sm text-ink-gray-5">
					No contacts or addresses yet.
				</p>
			</div>
		</section>

		<section v-if="showBank" class="summary-card">
			<header class="summary-head">
				<h3>Bank details</h3>
				<Button
					v-if="editable"
					size="sm"
					variant="subtle"
					icon-left="lucide-pencil"
					label="Edit"
					@click="emit('edit', 'bank')"
				/>
			</header>
			<dl class="summary-grid">
				<div v-for="[label, value] in bank" :key="label as string">
					<dt>{{ label }}</dt>
					<dd>{{ value || "—" }}</dd>
				</div>
			</dl>
		</section>

		<section class="summary-card">
			<header class="summary-head">
				<h3>Supporting documents</h3>
				<Button
					v-if="editable"
					size="sm"
					variant="subtle"
					icon-left="lucide-pencil"
					label="Edit"
					@click="emit('edit', 'documents')"
				/>
			</header>
			<p v-if="!documents.length" class="text-p-sm text-ink-gray-5">No documents needed.</p>
			<div v-else class="divide-y divide-outline-gray-1">
				<div
					v-for="item in documents"
					:key="item.document_type"
					class="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
				>
					<div class="min-w-0">
						<p class="truncate text-base font-medium text-ink-gray-8">
							{{ item.document_type }}
							<span
								v-if="item.is_mandatory"
								class="text-p-sm font-normal text-ink-gray-5"
							>
								· required
							</span>
						</p>
						<p class="text-p-xs text-ink-gray-5">
							{{
								[
									item.document_number ? `Ref ${item.document_number}` : null,
									item.issue_date ? `Issued ${item.issue_date}` : null,
									item.expiry_date ? `Expires ${item.expiry_date}` : null,
								]
									.filter(Boolean)
									.join(" · ") || "No reference details"
							}}
						</p>
					</div>
					<a
						v-if="item.attachment"
						:href="item.attachment"
						target="_blank"
						class="flex shrink-0 items-center gap-1 text-p-sm font-medium text-ink-gray-8 underline"
					>
						<i class="lucide-external-link size-3.5" aria-hidden="true" />
						View
					</a>
					<Badge
						v-else
						class="shrink-0"
						:theme="item.is_mandatory ? 'red' : 'gray'"
						variant="subtle"
						label="Not attached"
					/>
				</div>
			</div>
		</section>
	</div>
</template>

<style scoped>
.summary-card {
	border: 1px solid var(--outline-gray-2);
	border-radius: 0.75rem;
	padding: 1rem;
}

.summary-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	margin-bottom: 0.75rem;
}

.summary-head h3 {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ink-gray-9);
}

.summary-grid {
	display: grid;
	gap: 0.75rem 1.5rem;
}

@media (min-width: 640px) {
	.summary-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}

.summary-grid dt {
	font-size: 0.6875rem;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: var(--ink-gray-5);
}

.summary-grid dd {
	font-size: 0.875rem;
	color: var(--ink-gray-8);
	overflow-wrap: anywhere;
}
</style>
