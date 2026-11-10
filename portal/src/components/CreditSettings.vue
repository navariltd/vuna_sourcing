<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { Alert, Avatar, Badge, Button, Spinner } from "frappe-ui";
import EmptyState from "@/components/EmptyState.vue";
import { useCreditStatus } from "@/composables/useCreditStatus";
import { usePortalSettings } from "@/composables/usePortalSettings";
import { CREDIT_STATE_LABEL, CREDIT_STATE_THEME } from "@/data/credit";
import type { CompanyCredit } from "@/data/credit";
import { money } from "@/data/purchase";

const credit = useCreditStatus();
const settings = usePortalSettings();
const router = useRouter();

onMounted(() => credit.reload());

const BAR_TONE: Record<CompanyCredit["state"], string> = {
	over: "bg-surface-red-6",
	near: "bg-surface-amber-5",
	within: "bg-surface-green-6",
};

function guidance(row: CompanyCredit) {
	if (row.state === "over") {
		return {
			icon: "lucide-circle-alert",
			tone: "border-outline-red-2 bg-surface-red-1 text-ink-red-7",
			text: `Pay ${money(
				row.over_by,
				row.currency
			)} to get back within your limit. Any payment above that frees up room for new orders.`,
		};
	}
	if (row.state === "near") {
		return {
			icon: "lucide-triangle-alert",
			tone: "border-outline-amber-2 bg-surface-amber-1 text-ink-amber-7",
			text: `You have ${money(
				row.available,
				row.currency
			)} left before you reach your limit.`,
		};
	}
	return {
		icon: "lucide-circle-check",
		tone: "border-outline-green-2 bg-surface-green-1 text-ink-green-7",
		text: `You can order up to ${money(row.available, row.currency)} more on credit.`,
	};
}

function seeInvoices() {
	settings.open.value = false;
	router.push({ name: "CustomerStatement" });
}
</script>

<template>
	<div class="flex flex-col gap-4">
		<div class="flex items-center justify-between gap-3">
			<p class="text-p-sm text-ink-gray-6">
				{{ credit.rows.value.length ? "One card for each company you buy from." : "" }}
			</p>
			<Button
				variant="ghost"
				icon="lucide-refresh-cw"
				aria-label="Refresh credit details"
				:loading="credit.loading.value"
				@click="credit.reload()"
			/>
		</div>

		<div
			v-if="credit.loading.value && !credit.rows.value.length"
			class="flex justify-center py-10"
		>
			<Spinner class="size-5" />
		</div>

		<Alert
			v-else-if="credit.error.value"
			theme="red"
			title="We could not load your credit"
			:description="credit.error.value"
		/>

		<EmptyState
			v-else-if="!credit.rows.value.length"
			icon="lucide-wallet"
			title="No credit limit on your account"
			description="Your account does not have a credit limit with any company, so there is nothing to track here."
		/>

		<article
			v-for="row in credit.rows.value"
			v-else
			:key="row.company"
			class="card flex flex-col gap-4 p-4"
			:aria-label="`Credit with ${row.company}`"
		>
			<header class="flex items-center gap-3">
				<Avatar :label="row.company" size="lg" shape="square" />
				<p class="min-w-0 flex-1 truncate text-base font-semibold text-ink-gray-9">
					{{ row.company }}
				</p>
				<Badge
					:theme="CREDIT_STATE_THEME[row.state]"
					:label="CREDIT_STATE_LABEL[row.state]"
				/>
			</header>

			<div>
				<div class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
					<p class="text-p-sm text-ink-gray-6">
						<span class="text-xl font-semibold tabular-nums text-ink-gray-9">
							{{ money(row.used, row.currency) }}
						</span>
						used of {{ money(row.credit_limit, row.currency) }}
					</p>
					<p
						class="text-p-sm font-medium tabular-nums"
						:class="row.state === 'over' ? 'text-ink-red-7' : 'text-ink-gray-7'"
					>
						{{
							row.state === "over"
								? `${money(row.over_by, row.currency)} over`
								: `${money(row.available, row.currency)} available`
						}}
					</p>
				</div>
				<div
					class="mt-2 h-2 overflow-hidden rounded-full bg-surface-gray-2"
					role="meter"
					:aria-valuenow="row.used_percent"
					aria-valuemin="0"
					aria-valuemax="100"
					:aria-label="`${row.used_percent}% of your credit limit used`"
				>
					<div
						class="h-full rounded-full transition-[width] duration-500"
						:class="BAR_TONE[row.state]"
						:style="{ width: `${Math.min(row.used_percent, 100)}%` }"
					/>
				</div>
				<p class="mt-1 text-p-xs tabular-nums text-ink-gray-5">
					{{ row.used_percent }}% of your limit
				</p>
			</div>

			<dl class="grid grid-cols-1 gap-3 sm:grid-cols-3">
				<div class="card-muted p-3">
					<dt class="text-xs text-ink-gray-5">Credit limit</dt>
					<dd class="mt-0.5 text-base font-semibold tabular-nums text-ink-gray-9">
						{{ money(row.credit_limit, row.currency) }}
					</dd>
				</div>
				<div class="card-muted p-3">
					<dt class="text-xs text-ink-gray-5">Unpaid invoices</dt>
					<dd class="mt-0.5 text-base font-semibold tabular-nums text-ink-gray-9">
						{{ money(row.unpaid_invoices, row.currency) }}
					</dd>
				</div>
				<div class="card-muted p-3">
					<dt class="text-xs text-ink-gray-5">Confirmed, not yet invoiced</dt>
					<dd class="mt-0.5 text-base font-semibold tabular-nums text-ink-gray-9">
						{{ money(row.not_yet_invoiced, row.currency) }}
					</dd>
				</div>
			</dl>

			<p
				class="flex items-start gap-2 rounded-6 border p-3 text-p-sm"
				:class="guidance(row).tone"
			>
				<i :class="guidance(row).icon" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
				<span>{{ guidance(row).text }}</span>
			</p>

			<div class="flex flex-wrap gap-2">
				<Button
					variant="solid"
					icon-left="lucide-receipt"
					label="See unpaid invoices"
					@click="seeInvoices"
				/>
			</div>
		</article>

		<p v-if="credit.rows.value.length" class="text-p-xs text-ink-gray-5">
			You can always send orders from the portal. Orders above your limit may be held until a
			payment comes in. Amounts are in each company's currency.
		</p>
	</div>
</template>
