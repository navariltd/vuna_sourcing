<script setup lang="ts">
import { computed, watch } from "vue";
import { Button, Spinner } from "frappe-ui";
import { ListView } from "frappe-ui/experimental";
import { useRouter } from "vue-router";
import PageContainer from "@/components/PageContainer.vue";
import EmptyState from "@/components/EmptyState.vue";
import { money, shortDate } from "@/data/purchase";
import { customerStatement, supplierStatement } from "@/data/statement";
import type { Statement, StatementRow } from "@/data/statement";
import { usePortalStore } from "@/stores/portal";
import { LOOKS } from "@/data/accents";
import { useIsMobile } from "@/composables/useViewport";

const props = defineProps<{ side: "Customer" | "Supplier" }>();

const portal = usePortalStore();
const router = useRouter();
const isMobile = useIsMobile();

const isCustomer = props.side === "Customer";
const request = isCustomer ? customerStatement : supplierStatement;

const copy = isCustomer
	? { reference: "Your PO", notes: "Credit notes" }
	: { reference: "Your invoice", notes: "Debit notes" };

const party = computed(() =>
	portal.activeParty?.party_type === props.side ? portal.activeParty.name : null
);

const statement = computed<Statement | null>(() => request.data ?? null);
const sections = computed(() => statement.value?.companies ?? []);

function load() {
	if (!party.value) {
		request.reset();
		return;
	}
	request.fetch(isCustomer ? { customer: party.value } : { supplier: party.value });
}

watch(party, load, { immediate: true });

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
				v-if="party"
				variant="subtle"
				icon="lucide-refresh-cw"
				aria-label="Refresh"
				:loading="request.loading"
				@click="load"
			/>
		</template>

		<EmptyState
			v-if="!party"
			icon="lucide-store"
			:title="`Switch to a ${side.toLowerCase()} account`"
			:description="`This statement belongs to your ${side.toLowerCase()} accounts. Pick one at the top of the sidebar.`"
		/>

		<div v-else-if="request.loading && !statement" class="flex justify-center py-16">
			<Spinner class="size-5" />
		</div>

		<EmptyState
			v-else-if="request.error"
			icon="lucide-file-x"
			title="We cannot show this statement right now"
			description="Please try again in a moment. If it keeps happening, contact our team."
		/>

		<EmptyState
			v-else-if="!sections.length || sections.every((s) => !s.rows.length)"
			icon="lucide-circle-check"
			title="No pending invoices"
			description="Every invoice is paid in full."
		/>

		<div v-else class="space-y-8">
			<section v-for="section in sections" :key="section.company" class="space-y-4">
				<h2 v-if="sections.length > 1" class="text-base font-semibold text-ink-gray-8">
					{{ section.company }}
				</h2>

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
