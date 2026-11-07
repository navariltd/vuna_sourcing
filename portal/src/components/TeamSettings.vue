<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
	Avatar,
	Badge,
	Button,
	Dialog,
	Dropdown,
	ErrorMessage,
	FormControl,
	Spinner,
	toast,
} from "frappe-ui";
import BranchPicker from "@/components/BranchPicker.vue";
import { errorText } from "@/data/orders";
import {
	MEMBER_STATUS_THEME,
	branchSummary,
	inviteMember,
	removeMember,
	resendInvitation,
	teamResource,
	updateMemberBranches,
} from "@/data/team";
import type { Team, TeamMember } from "@/data/team";
import { usePortalStore } from "@/stores/portal";
import { isOk } from "@/types/api";
import type { ApiResponse } from "@/types/api";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const portal = usePortalStore();

const customer = computed(() =>
	portal.activeParty?.party_type === "Customer" ? portal.activeParty : null
);

const team = computed(() =>
	customer.value && portal.user ? teamResource(portal.user.name, customer.value.name) : null
);

watch(team, (resource) => resource?.reload(), { immediate: true });

const members = computed<TeamMember[]>(
	() => (team.value?.data?.data as Team | undefined)?.members ?? []
);
const loading = computed(() => !!team.value?.loading && !team.value?.data);
const loadError = computed(() =>
	team.value?.error ? errorText(team.value.error, "We could not load your team.") : null
);
const othersCount = computed(() => members.value.filter((member) => !member.is_you).length);

function showMembers(updated: TeamMember[] | undefined) {
	if (!team.value || !customer.value || !updated) return;
	team.value.setData({
		...(team.value.data ?? {}),
		data: { customer: customer.value.name, members: updated },
	});
}

async function run<T extends { members: TeamMember[] } | null>(
	action: () => Promise<ApiResponse<T>>,
	error: { value: string | null },
	fallback: string
) {
	error.value = null;
	try {
		const response = await action();
		if (!isOk(response)) {
			error.value = response.message || fallback;
			return false;
		}
		showMembers(response.data?.members);
		toast.success(response.message || "Saved.");
		return true;
	} catch (failure) {
		error.value = errorText(failure, fallback);
		return false;
	}
}

const inviting = ref(false);
const sendingInvite = ref(false);
const inviteError = ref<string | null>(null);
const invite = reactive({ first_name: "", last_name: "", email: "", branches: [] as string[] });

const inviteReady = computed(
	() =>
		!!invite.first_name.trim() &&
		!!invite.last_name.trim() &&
		EMAIL_PATTERN.test(invite.email.trim())
);

function openInvite() {
	Object.assign(invite, { first_name: "", last_name: "", email: "", branches: [] });
	inviteError.value = null;
	inviting.value = true;
}

async function sendInvite() {
	if (!customer.value || !inviteReady.value) return;
	sendingInvite.value = true;
	const sent = await run(
		() =>
			inviteMember(customer.value!.name, {
				first_name: invite.first_name.trim(),
				last_name: invite.last_name.trim(),
				email: invite.email.trim(),
				branches: invite.branches,
			}),
		inviteError,
		"We could not send the invitation."
	);
	sendingInvite.value = false;
	if (sent) inviting.value = false;
}

const editing = ref<TeamMember | null>(null);
const editBranches = ref<string[]>([]);
const savingBranches = ref(false);
const editError = ref<string | null>(null);

const editingOpen = computed({
	get: () => !!editing.value,
	set: (open: boolean) => {
		if (!open) editing.value = null;
	},
});

function openEdit(member: TeamMember) {
	editing.value = member;
	editBranches.value = member.branches.map((branch) => branch.name);
	editError.value = null;
}

async function saveBranches() {
	if (!customer.value || !editing.value) return;
	savingBranches.value = true;
	const member = editing.value;
	const saved = await run(
		() => updateMemberBranches(customer.value!.name, member.user, editBranches.value),
		editError,
		"We could not change their branches."
	);
	savingBranches.value = false;
	if (saved) editing.value = null;
}

const removing = ref<TeamMember | null>(null);
const removingMember = ref(false);
const removeError = ref<string | null>(null);

const removingOpen = computed({
	get: () => !!removing.value,
	set: (open: boolean) => {
		if (!open) removing.value = null;
	},
});

function openRemove(member: TeamMember) {
	removing.value = member;
	removeError.value = null;
}

async function confirmRemove() {
	if (!customer.value || !removing.value) return;
	removingMember.value = true;
	const member = removing.value;
	const removed = await run(
		() => removeMember(customer.value!.name, member.user),
		removeError,
		"We could not remove them."
	);
	removingMember.value = false;
	if (removed) removing.value = null;
}

async function resend(member: TeamMember) {
	if (!customer.value) return;
	const error = { value: null as string | null };
	const sent = await run(
		() => resendInvitation(customer.value!.name, member.user),
		error,
		"We could not resend the invitation."
	);
	if (!sent && error.value) toast.error(error.value);
}

function actionsFor(member: TeamMember) {
	return [
		{ label: "Change branches", icon: "lucide-map-pin", onClick: () => openEdit(member) },
		...(member.status === "Invited"
			? [{ label: "Resend invitation", icon: "lucide-send", onClick: () => resend(member) }]
			: []),
		{
			label: "Remove access",
			icon: "lucide-user-minus",
			theme: "red" as const,
			onClick: () => openRemove(member),
		},
	];
}
</script>

<template>
	<div class="flex flex-col gap-4">
		<div class="flex flex-wrap items-start justify-between gap-3">
			<p class="max-w-md text-p-sm text-ink-gray-6">
				People at {{ customer?.title }} who can sign in to the portal, and the branches
				each one sees.
			</p>
			<Button
				variant="solid"
				label="Invite someone"
				icon-left="lucide-user-plus"
				@click="openInvite"
			/>
		</div>

		<div v-if="loading" class="flex justify-center py-10">
			<Spinner class="size-5" />
		</div>

		<ErrorMessage v-else-if="loadError" :message="loadError" />

		<div v-else class="divide-y rounded-6 border">
			<div
				v-for="member in members"
				:key="member.user"
				class="flex items-center gap-3 px-3 py-2.5"
			>
				<Avatar :image="member.image || undefined" :label="member.full_name" size="lg" />

				<div class="min-w-0 flex-1">
					<div class="flex min-w-0 items-center gap-1.5">
						<span class="truncate text-base font-medium text-ink-gray-8">
							{{ member.full_name }}
						</span>
						<Badge v-if="member.is_you" theme="gray" variant="subtle" label="You" />
						<Badge
							v-if="member.is_account_admin"
							theme="blue"
							variant="subtle"
							label="Admin"
						/>
					</div>
					<p class="truncate text-p-sm text-ink-gray-5">{{ member.user }}</p>
					<p
						class="flex items-center gap-1 truncate text-p-sm text-ink-gray-6 sm:hidden"
					>
						<i class="lucide-map-pin size-3.5 shrink-0" aria-hidden="true" />
						{{ branchSummary(member) }}
					</p>
				</div>

				<span
					class="hidden max-w-[10rem] shrink-0 truncate text-p-sm text-ink-gray-6 sm:block"
					:title="member.branches.map((branch) => branch.title).join(', ')"
				>
					{{ branchSummary(member) }}
				</span>

				<Badge
					v-if="member.status !== 'Active'"
					class="shrink-0"
					:theme="MEMBER_STATUS_THEME[member.status]"
					variant="subtle"
					:label="member.status"
				/>

				<Dropdown
					v-if="member.editable"
					:options="actionsFor(member)"
					placement="bottom-end"
				>
					<Button
						variant="ghost"
						icon="lucide-ellipsis"
						:aria-label="`Manage ${member.full_name}`"
					/>
				</Dropdown>
				<span v-else class="size-7 shrink-0" aria-hidden="true" />
			</div>

			<div v-if="!othersCount" class="px-3 py-6 text-center">
				<p class="text-base font-medium text-ink-gray-7">Just you so far</p>
				<p class="mt-1 text-p-sm text-ink-gray-5">
					Invite the people who order or follow invoices for your branches.
				</p>
			</div>
		</div>

		<p class="text-p-sm text-ink-gray-5">
			To make someone an admin or change another admin, contact our team.
		</p>

		<Dialog
			v-model:open="inviting"
			title="Invite someone"
			message="They get an email with a link to set a password, then they can sign in."
			icon="lucide-user-plus"
			:actions="[
				{
					label: 'Send invitation',
					variant: 'solid',
					loading: sendingInvite,
					disabled: !inviteReady,
					onClick: sendInvite,
				},
			]"
		>
			<form class="flex flex-col gap-3" @submit.prevent="sendInvite">
				<div class="grid gap-3 sm:grid-cols-2">
					<FormControl
						v-model="invite.first_name"
						label="First name"
						autocomplete="off"
					/>
					<FormControl v-model="invite.last_name" label="Last name" autocomplete="off" />
				</div>
				<FormControl
					v-model="invite.email"
					label="Email"
					type="email"
					autocomplete="off"
				/>
				<BranchPicker
					v-model="invite.branches"
					label="Branches"
					description="Leave empty to give them every branch."
				/>
				<ErrorMessage v-if="inviteError" :message="inviteError" />
			</form>
		</Dialog>

		<Dialog
			v-model:open="editingOpen"
			:title="`Branches for ${editing?.full_name ?? ''}`"
			message="They only see orders, deliveries and invoices for these branches."
			icon="lucide-map-pin"
			:actions="[
				{
					label: 'Save',
					variant: 'solid',
					loading: savingBranches,
					onClick: saveBranches,
				},
			]"
		>
			<div class="flex flex-col gap-3">
				<BranchPicker
					v-model="editBranches"
					label="Branches"
					description="Leave empty to give them every branch."
				/>
				<ErrorMessage v-if="editError" :message="editError" />
			</div>
		</Dialog>

		<Dialog
			v-model:open="removingOpen"
			:title="`Remove ${removing?.full_name ?? ''}?`"
			:message="`They can no longer sign in for ${
				customer?.title ?? 'this account'
			}. Orders and requests they made stay.`"
			icon="lucide-user-minus"
			theme="red"
			:actions="[
				{
					label: 'Remove access',
					variant: 'solid',
					theme: 'red',
					loading: removingMember,
					onClick: confirmRemove,
				},
			]"
		>
			<ErrorMessage v-if="removeError" :message="removeError" />
		</Dialog>
	</div>
</template>
