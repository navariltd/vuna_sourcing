<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Alert, Avatar, Button, Spinner } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import { useRouter } from "vue-router";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import { money, shortDate } from "@/data/purchase";
import { fetchStatement } from "@/data/statement";
import type { Statement, StatementRow } from "@/data/statement";
import { errorText } from "@/data/orders";
import { isOk } from "@/types/api";
import { usePortalStore } from "@/stores/portal";
import { LOOKS } from "@/data/accents";
import { useIsMobile } from "@/composables/useViewport";

const props = defineProps<{ side: "Customer" | "Supplier" }>();

const portal = usePortalStore();
const router = useRouter();
const isMobile = useIsMobile();

const isCustomer = props.side === "Customer";

const copy = isCustomer
	? { reference: "Your PO", notes: "Credit notes" }
	: { reference: "Your invoice", notes: "Debit notes" };

const party = computed(() =>
	portal.activeParty?.party_type === props.side ? portal.activeParty.name : null
);

const statement = ref<Statement | null>(null);
const company = ref<string | null>(null);
const loading = ref(false);
const loadError = ref<string | null>(null);
let request = 0;

const companies = computed(() => statement.value?.companies ?? []);
const section = computed(() => statement.value?.section ?? null);
const sections = computed(() => (section.value ? [section.value] : []));
const choosingCompany = computed(
	() => !!statement.value && companies.value.length > 1 && !company.value
);

async function load() {
	const current = ++request;
	if (!party.value) {
		statement.value = null;
		return;
	}
	loading.value = true;
	loadError.value = null;
	try {
		const response = await fetchStatement(props.side, party.value, company.value);
		if (current !== request) return;
		if (!isOk(response)) {
			loadError.value =
				response.message || "We cannot show your pending invoices right now.";
			return;
		}
		statement.value = response.data;
		company.value = response.data.company;
	} catch (error) {
		if (current === request)
			loadError.value = errorText(error, "We cannot show your pending invoices right now.");
	} finally {
		if (current === request) loading.value = false;
	}
}

function chooseCompany(name: string | null) {
	if (name === company.value) return;
	company.value = name;
	if (statement.value) statement.value = { ...statement.value, section: null };
	load();
}

watch(
	party,
	() => {
		company.value = null;
		statement.value = null;
		load();
	},
	{ immediate: true }
);

function reference(row: StatementRow) {
	return (isCustomer ? row.po_no : row.bill_no) || "—";
}

const columns = computed(() =>
	isMobile.value
		? [
				{ label: "Document", key: "voucher_no", width: "minmax(150px, 2fr)" },
				{
					label: "Outstanding",
					key: "outstanding",
					width: "minmax(110px, 1fr)",
					align: "right",
				},
		  ]
		: [
				{ label: "Document", key: "voucher_no", width: "minmax(180px, 2fr)" },
				{ label: "Due", key: "due_date", width: "minmax(130px, 1.2fr)" },
				{ label: copy.reference, key: "reference", width: "minmax(110px, 1fr)" },
				{
					label: "Invoiced",
					key: "invoiced",
					width: "minmax(110px, 1fr)",
					align: "right",
				},
				{
					label: "Outstanding",
					key: "outstanding",
					width: "minmax(120px, 1fr)",
					align: "right",
				},
		  ]
);

const options = {
	selectable: false,
	showTooltip: false,
	rowHeight: 52,
	onRowClick: (row: StatementRow) => {
		const route = documentRoute(row);
		if (route) router.push(route);
	},
};

function documentRoute(row: StatementRow) {
	if (row.voucher_type === "Sales Invoice") {
		return { name: "SalesInvoiceDetail", params: { name: row.voucher_no } };
	}
	if (row.voucher_type === "Purchase Invoice") {
		return { name: "PurchaseInvoiceDetail", params: { name: row.voucher_no } };
	}
	return null;
}
</script>

<template>
	<PageContainer
		:look="isCustomer ? LOOKS.receivable : LOOKS.payable"
		wide
		:title="'Pending Invoices'"
	>
		<template #actions>
			<Button
				v-if="party && company"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="loading"
				@click="load"
			/>
		</template>

		<div
			v-if="party && companies.length > 1 && company"
			class="mb-5 flex flex-wrap items-center gap-2"
			role="group"
			aria-label="Company"
		>
			<span class="text-p-sm text-ink-gray-6">Company</span>
			<button
				v-for="name in companies"
				:key="name"
				type="button"
				class="flex h-8 items-center gap-1.5 rounded-full border px-3 text-base font-medium transition-colors"
				:class="
					company === name
						? 'border-outline-gray-9 bg-surface-gray-10 text-ink-base'
						: 'border-outline-gray-2 bg-surface-base text-ink-gray-8 hover:bg-surface-gray-1'
				"
				:aria-pressed="company === name"
				@click="chooseCompany(name)"
			>
				{{ name }}
			</button>
		</div>

		<Alert
			v-if="statement?.branch_limited && section"
			class="mb-5"
			theme="blue"
			title="Showing invoices for your branches"
			description="Payments that are not yet matched to an invoice are not branch specific, so they are not listed here. Your account admin sees the full statement."
		/>

		<EmptyState
			v-if="!party"
			icon="lucide-store"
			:title="`Switch to a ${side.toLowerCase()} account`"
			:description="`This statement belongs to your ${side.toLowerCase()} accounts. Pick one at the top of the sidebar.`"
		/>

		<div v-else-if="loading && !section" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="loadError"
			icon="lucide-file-x"
			title="We cannot show your pending invoices right now"
			:description="loadError"
		>
			<Button variant="subtle" label="Try again" @click="load" />
		</EmptyState>

		<section
			v-else-if="choosingCompany"
			class="mx-auto max-w-2xl py-4"
			aria-labelledby="statement-company"
		>
			<h2 id="statement-company" class="text-lg font-semibold text-ink-gray-9">
				Which company's invoices would you like to see?
			</h2>
			<p class="mt-1 text-p-base text-ink-gray-6">
				You deal with {{ companies.length }} of our companies. Each keeps its own invoices
				and balance.
			</p>
			<div class="mt-4 grid gap-3 sm:grid-cols-2">
				<button
					v-for="name in companies"
					:key="name"
					type="button"
					class="flex items-center gap-3 rounded-8 border border-outline-gray-2 bg-surface-base p-4 text-left transition-[border-color,box-shadow] hover:border-outline-gray-4 hover:shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-4"
					@click="chooseCompany(name)"
				>
					<Avatar :label="name" size="xl" shape="square" />
					<span class="min-w-0 flex-1 truncate text-base font-semibold text-ink-gray-9">
						{{ name }}
					</span>
					<i class="lucide-chevron-right size-4 text-ink-gray-5" aria-hidden="true" />
				</button>
			</div>
		</section>

		<EmptyState
			v-else-if="!section || !section.rows.length"
			icon="lucide-circle-check"
			title="No pending invoices"
			:description="
				company
					? `Every invoice from ${company} is paid in full.`
					: 'Every invoice is paid in full.'
			"
		/>

		<div v-else class="space-y-8">
			<section v-for="section in sections" :key="section.company" class="space-y-4">
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
					<div class="col-span-2 rounded-6 border p-4 sm:col-span-1">
						<p class="text-xs uppercase tracking-wide text-ink-gray-5">Outstanding</p>
						<p class="mt-1 text-xl font-semibold text-ink-gray-9">
							{{ money(section.totals.outstanding, section.currency) }}
						</p>
					</div>
					<div class="rounded-6 border p-4">
						<p class="text-xs uppercase tracking-wide text-ink-gray-5">Invoiced</p>
						<p class="mt-1 text-lg text-ink-gray-8">
							{{ money(section.totals.invoiced, section.currency) }}
						</p>
					</div>
					<div class="rounded-6 border p-4">
						<p class="text-xs uppercase tracking-wide text-ink-gray-5">Paid</p>
						<p class="mt-1 text-lg text-ink-gray-8">
							{{ money(section.totals.paid, section.currency) }}
						</p>
					</div>
					<div class="rounded-6 border p-4">
						<p class="text-xs uppercase tracking-wide text-ink-gray-5">
							{{ copy.notes }}
						</p>
						<p class="mt-1 text-lg text-ink-gray-8">
							{{ money(section.totals.credit_note, section.currency) }}
						</p>
					</div>
				</div>

				<ListView
					row-key="voucher_no"
					:columns="columns"
					:rows="section.rows"
					:options="options"
				>
					<template #cell="{ column, row }">
						<span v-if="column.key === 'voucher_no'" class="flex min-w-0 flex-col">
							<span class="truncate text-base text-ink-gray-8">{{
								row.voucher_no
							}}</span>
							<span class="truncate text-xs text-ink-gray-5">
								<template v-if="isMobile && row.due_date">
									Due {{ shortDate(row.due_date) }}
								</template>
								<template v-else>
									{{ row.voucher_type }} · {{ shortDate(row.posting_date) }}
								</template>
							</span>
						</span>

						<span
							v-else-if="column.key === 'due_date'"
							class="text-base text-ink-gray-7"
						>
							{{ shortDate(row.due_date) }}
							<span v-if="row.age > 0" class="text-ink-gray-5"
								>· {{ row.age }} days</span
							>
						</span>

						<span
							v-else-if="column.key === 'reference'"
							class="truncate text-base text-ink-gray-7"
						>
							{{ reference(row) }}
						</span>

						<span
							v-else
							class="block w-full text-right text-base"
							:class="
								column.key === 'outstanding'
									? 'font-medium text-ink-gray-9'
									: 'text-ink-gray-7'
							"
						>
							{{ money(row[column.key], row.currency) }}
						</span>
					</template>
				</ListView>
			</section>
		</div>
	</PageContainer>
</template>
