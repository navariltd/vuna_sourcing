<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Button, ErrorMessage, FormControl, Spinner, createResource } from "frappe-ui";
import type { ApiResponse, SignupContext, SignupResult } from "@/types/api";
import { PARTY_COPY, joinNouns } from "@/data/parties";
import type { PartyType } from "@/data/parties";
import { loginUrl } from "@/router";

const form = reactive({ first_name: "", last_name: "", email: "" });
const touched = reactive({ email: false });
const submitting = ref(false);
const formError = ref<string | null>(null);
const result = ref<ApiResponse<SignupResult> | null>(null);

const context = createResource({
	url: "vuna_sourcing.api.signup.get_signup_context",
	auto: false,
});

onMounted(() => context.fetch());

const signupContext = computed<SignupContext | null>(
	() => (context.data as ApiResponse<SignupContext> | null)?.data ?? null
);

const isOpen = computed(() => !!signupContext.value?.is_open);
const appTitle = computed(() => signupContext.value?.app_title ?? "Portal");

const partyTypes = computed(() => (signupContext.value?.party_types ?? []) as PartyType[]);
const nouns = computed(() => joinNouns(partyTypes.value) || "supplier or customer");
const contactEmail = computed<string | null>(() => signupContext.value?.contact_email ?? null);
const closedMessage = computed(() => signupContext.value?.closed_message ?? null);
const logo = computed(() => signupContext.value?.logo ?? null);

const emailLooksValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()));

const emailHint = computed(() =>
	touched.email && form.email.trim() && !emailLooksValid.value
		? "Enter a complete email address, like you@company.com"
		: null
);

const canSubmit = computed(
	() => !!form.first_name.trim() && !!form.last_name.trim() && emailLooksValid.value
);

const BENEFITS = [
	{
		icon: "lucide-clipboard-check",
		title: "Know exactly what to submit",
		body: "A clear list of the details and documents we need for your kind of business, so there is no back-and-forth.",
	},
	{
		icon: "lucide-users",
		title: "One account, either side of the deal",
		body: "Apply to supply us, to buy from us, or both. You choose when you apply, and can add the other later.",
	},
	{
		icon: "lucide-eye",
		title: "Track every application",
		body: "See where each application stands and exactly what needs your attention if one comes back.",
	},
];

function goToLogin() {
	window.location.href = loginUrl();
}

async function submit() {
	if (!canSubmit.value || submitting.value) return;
	submitting.value = true;
	formError.value = null;

	try {
		result.value = (await createResource({
			url: "vuna_sourcing.api.signup.sign_up",
			method: "POST",
		}).submit({ ...form })) as ApiResponse<SignupResult>;
	} catch (error: any) {
		formError.value =
			error?.messages?.[0] || error?.message || "Something went wrong. Please try again.";
	} finally {
		submitting.value = false;
	}
}
</script>

<template>
	<div class="min-h-full bg-surface-white text-ink-gray-9 lg:flex">
		<aside
			class="relative hidden overflow-hidden bg-surface-gray-5 lg:flex lg:w-[46%] lg:flex-col"
		>
			<div
				aria-hidden="true"
				class="pointer-events-none absolute -right-32 -top-32 size-[34rem] rounded-full border-[5rem] border-surface-gray-4/50"
			/>

			<div
				aria-hidden="true"
				class="pointer-events-none absolute -bottom-48 -left-32 size-[30rem] rounded-full bg-surface-gray-4/40 blur-3xl"
			/>

			<div class="relative flex h-full flex-col px-12 py-10 xl:px-16">
				<div class="flex flex-col items-start gap-3">
					<span class="text-sm font-semibold text-ink-gray-9">
						{{ appTitle }}
					</span>

					<div
						class="rounded-full flex size-40 items-center justify-center overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-outline-gray-2"
					>
						<img
							v-if="logo"
							:src="logo"
							:alt="appTitle"
							class="size-full rounded-full object-contain p-2"
						/>

						<span v-else class="text-lg font-bold text-ink-gray-8">
							{{ appTitle.charAt(0) }}
						</span>
					</div>
				</div>

				<div class="relative mt-auto max-w-xl pb-8 pt-20">
					<div
						class="mb-5 inline-flex items-center gap-2 rounded-full border border-outline-gray-2 bg-white/70 px-3 py-1.5 text-xs font-medium text-ink-gray-7 backdrop-blur"
					>
						<span class="size-1.5 rounded-full bg-ink-green-6" />
						One account. Multiple relationships.
					</div>

					<h1
						class="text-4xl font-semibold leading-[1.08] tracking-[-0.03em] text-ink-gray-9 xl:text-5xl"
					>
						Less paperwork.
						<span class="text-ink-gray-5"> More business. </span>
					</h1>

					<p class="mt-5 max-w-lg text-base leading-7 text-ink-gray-6">
						Create one account and manage your relationship with
						{{ appTitle }} from a single place — whether you supply us, buy from us, or
						both.
					</p>

					<div
						class="mt-10 grid gap-3"
						:class="partyTypes.length > 1 ? 'sm:grid-cols-2' : 'sm:max-w-sm'"
					>
						<div
							v-for="partyType in partyTypes.length
								? partyTypes
								: (['Supplier', 'Customer'] as PartyType[])"
							:key="partyType"
							class="group rounded-5 border border-outline-gray-2 bg-white/80 p-4 backdrop-blur transition-all hover:-translate-y-0.5 hover:bg-white hover:shadow-lg"
						>
							<div class="flex items-start justify-between">
								<div
									class="flex size-9 items-center justify-center rounded-lg bg-surface-gray-2"
								>
									<i
										:class="[
											PARTY_COPY[partyType].icon,
											'size-4 text-ink-gray-8',
										]"
									/>
								</div>

								<i
									class="lucide-arrow-up-right size-4 text-ink-gray-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
								/>
							</div>

							<p class="mt-5 text-sm font-semibold text-ink-gray-9">
								{{ PARTY_COPY[partyType].headline }}
							</p>

							<p class="mt-1 text-xs font-medium text-ink-gray-5">
								{{ PARTY_COPY[partyType].noun }}
							</p>

							<p class="mt-3 text-xs leading-5 text-ink-gray-6">
								{{ PARTY_COPY[partyType].pitch }}
							</p>
						</div>
					</div>

					<div class="mt-8 space-y-3">
						<div
							v-for="item in BENEFITS"
							:key="item.title"
							class="flex items-start gap-3"
						>
							<div
								class="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-white ring-1 ring-outline-gray-2"
							>
								<i :class="[item.icon, 'size-3.5 text-ink-gray-8']" />
							</div>

							<div>
								<p class="text-sm font-medium text-ink-gray-8">
									{{ item.title }}
								</p>

								<p class="mt-0.5 text-xs leading-5 text-ink-gray-5">
									{{ item.body }}
								</p>
							</div>
						</div>
					</div>
				</div>

				<div class="flex items-center justify-between border-t border-outline-gray-2 pt-5">
					<p class="text-xs text-ink-gray-5">Secure partner onboarding</p>

					<a
						:href="loginUrl()"
						class="inline-flex items-center gap-1 text-xs font-medium text-ink-gray-8 hover:underline"
					>
						Sign in
						<i class="lucide-arrow-up-right size-3" />
					</a>
				</div>
			</div>
		</aside>

		<div
			class="flex items-center justify-between border-b border-outline-gray-2 px-5 py-4 lg:hidden"
		>
			<div class="flex flex-col items-start gap-3">
				<span class="text-sm font-semibold text-ink-gray-9">
					{{ appTitle }}
				</span>

				<div
					class="rounded-full flex size-16 items-center justify-center overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-outline-gray-2"
				>
					<img
						v-if="logo"
						:src="logo"
						:alt="appTitle"
						class="size-full rounded-full object-contain p-2"
					/>

					<span v-else class="text-lg font-bold text-ink-gray-8">
						{{ appTitle.charAt(0) }}
					</span>
				</div>
			</div>

			<a :href="loginUrl()" class="text-sm font-medium text-ink-gray-7"> Sign in </a>
		</div>

		<main
			class="flex min-h-[calc(100vh-66px)] flex-1 items-start justify-center overflow-y-auto px-5 py-10 sm:px-8 sm:py-14 lg:min-h-screen lg:items-center lg:px-12"
		>
			<div class="w-full max-w-[480px]">
				<div
					v-if="context.loading && !context.data"
					class="flex min-h-80 items-center justify-center"
				>
					<div class="text-center">
						<Spinner class="mx-auto size-5" />

						<p class="mt-3 text-sm text-ink-gray-5">Preparing your registration...</p>
					</div>
				</div>

				<div
					v-else-if="!isOpen"
					class="rounded-5 border border-outline-gray-2 bg-surface-white p-6 shadow-sm sm:p-8"
				>
					<div
						class="flex size-12 items-center justify-center rounded-xl bg-surface-amber-2"
					>
						<i class="lucide-mail-plus size-5 text-ink-amber-7" />
					</div>

					<p
						class="mt-6 text-xs font-semibold uppercase tracking-widest text-ink-gray-5"
					>
						Registration
					</p>

					<h1 class="mt-2 text-2xl font-semibold tracking-tight text-ink-gray-9">
						Registration is by invitation
					</h1>

					<p class="mt-3 text-sm leading-6 text-ink-gray-6">
						{{ closedMessage }}
					</p>

					<div
						v-if="contactEmail"
						class="mt-6 rounded-xl border border-outline-gray-2 bg-surface-gray-1 p-4"
					>
						<p class="text-xs text-ink-gray-5">Need access?</p>

						<a
							:href="`mailto:${contactEmail}?subject=Registration%20enquiry`"
							class="mt-1 block text-sm font-medium text-ink-gray-8 hover:underline"
						>
							{{ contactEmail }}
						</a>
					</div>

					<div class="mt-6 flex flex-col gap-2 sm:flex-row">
						<Button
							v-if="contactEmail"
							class="flex-1"
							variant="solid"
							label="Request an invitation"
							icon-left="lucide-mail"
							:href="`mailto:${contactEmail}?subject=Registration%20enquiry`"
						/>

						<Button
							class="flex-1"
							variant="ghost"
							label="Back to sign in"
							@click="goToLogin"
						/>
					</div>
				</div>

				<div
					v-else-if="result"
					class="rounded-5 border border-outline-gray-2 bg-surface-white p-6 text-center sm:p-8"
				>
					<div
						class="mx-auto flex size-14 items-center justify-center rounded-5"
						:class="result.ok ? 'bg-surface-green-2' : 'bg-surface-amber-2'"
					>
						<i
							:class="[
								result.ok ? 'lucide-mail-check' : 'lucide-circle-alert',
								'size-6',
								result.ok ? 'text-ink-green-7' : 'text-ink-amber-7',
							]"
						/>
					</div>

					<p
						class="mt-6 text-xs font-semibold uppercase tracking-widest text-ink-gray-5"
					>
						{{ result.ok ? "Almost there" : "Something went wrong" }}
					</p>

					<h1 class="mt-2 text-2xl font-semibold tracking-tight text-ink-gray-9">
						{{ result.ok ? "Check your email" : "We could not sign you up" }}
					</h1>

					<p class="mx-auto mt-3 max-w-sm text-sm leading-6 text-ink-gray-6">
						{{ result.message }}
					</p>

					<p v-if="!result.ok && contactEmail" class="mt-4 text-xs text-ink-gray-5">
						Still stuck?
						<a
							:href="`mailto:${contactEmail}`"
							class="font-medium text-ink-gray-8 underline underline-offset-2"
						>
							Contact support
						</a>
					</p>

					<div class="mt-7 flex flex-col gap-2 sm:flex-row sm:justify-center">
						<Button variant="solid" label="Go to sign in" @click="goToLogin" />

						<Button
							v-if="!result.ok"
							variant="ghost"
							label="Try again"
							@click="result = null"
						/>
					</div>
				</div>

				<form v-else class="space-y-7" @submit.prevent="submit">
					<div class="flex items-center gap-3">
						<div class="flex items-center gap-2"></div>

						<div class="h-px flex-1 bg-outline-gray-2" />
					</div>

					<div>
						<p class="text-xs font-semibold uppercase tracking-widest text-ink-gray-5">
							Get started
						</p>

						<h1
							class="mt-2 text-3xl font-semibold tracking-[-0.025em] text-ink-gray-9"
						>
							Create your account
						</h1>

						<p class="mt-3 max-w-md text-sm leading-6 text-ink-gray-6">
							We'll send a secure setup link to your email.
						</p>
					</div>

					<div
						class="rounded-5 border border-outline-gray-2 bg-surface-white p-5 sm:p-6"
					>
						<div class="space-y-5">
							<div class="grid gap-5 sm:grid-cols-2">
								<FormControl
									v-model="form.first_name"
									label="First name"
									placeholder="Jane"
									autocomplete="given-name"
									autofocus
									required
								/>

								<FormControl
									v-model="form.last_name"
									label="Last name"
									placeholder="Doe"
									autocomplete="family-name"
									required
								/>
							</div>

							<div>
								<FormControl
									v-model="form.email"
									type="email"
									label="Work email"
									placeholder="you@company.com"
									autocomplete="email"
									required
									@blur="touched.email = true"
								/>

								<p
									v-if="emailHint"
									class="mt-2 flex items-center gap-1.5 text-xs text-ink-amber-7"
								>
									<i class="lucide-circle-alert size-3.5" />
									{{ emailHint }}
								</p>

								<p
									v-else
									class="mt-2 flex items-center gap-1.5 text-xs text-ink-gray-5"
								>
									<i class="lucide-shield-check size-3.5" />
									We'll use this email to send your secure setup link.
								</p>
							</div>

							<ErrorMessage v-if="formError" :message="formError" />

							<Button
								class="w-full"
								variant="solid"
								size="md"
								label="Continue"
								:loading="submitting"
								:disabled="!canSubmit"
								icon-right="lucide-arrow-right"
								@click="submit"
							/>
						</div>
					</div>

					<div class="text-center">
						<p class="text-xs leading-5 text-ink-gray-5">
							By continuing, you'll create an account that can be used for your
							{{ nouns }} relationship.
						</p>

						<p class="mt-4 text-sm text-ink-gray-5">
							Already registered?

							<a
								:href="loginUrl()"
								class="font-medium text-ink-gray-8 underline underline-offset-2 hover:text-ink-gray-9"
							>
								Sign in
							</a>
						</p>
					</div>
				</form>
			</div>
		</main>
	</div>
</template>
