<script setup lang="ts">
import { computed } from "vue";
import { Button, ErrorMessage, FormControl, Select, Spinner } from "frappe-ui";
import QtyStepper from "@/components/QtyStepper.vue";
import { injectOrderDraft } from "@/composables/useOrderDraft";
import { money } from "@/data/purchase";

const emit = defineEmits<{ (e: "save"): void; (e: "send"): void; (e: "clear"): void }>();

const draft = injectOrderDraft();

const total = computed(() =>
	draft.priced.value && draft.lines.value.length
		? money(draft.priced.value.grand_total, draft.currency.value)
		: "—"
);

const nextStep = computed(() => draft.missing.value[0]?.label ?? null);
</script>

<template>
	<div class="flex min-h-0 flex-col">
		<div class="cart-body -mr-2 flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto pb-4 pr-2">
			<section aria-label="Items in your cart">
				<div
					v-if="!draft.lines.value.length"
					class="flex flex-col items-center gap-2 rounded-6 border border-dashed border-outline-gray-3 px-4 py-8 text-center"
				>
					<span class="grid size-10 place-items-center rounded-full bg-surface-gray-2">
						<i
							class="lucide-shopping-basket size-5 text-ink-gray-6"
							aria-hidden="true"
						/>
					</span>
					<p class="text-base font-medium text-ink-gray-8">Your cart is empty</p>
					<p class="text-p-sm text-ink-gray-6">
						Tap Add on an item to start your order.
					</p>
				</div>

				<div v-else class="mb-2 flex items-center justify-between gap-2">
					<p class="text-p-sm text-ink-gray-6">
						{{ draft.lines.value.length }}
						{{ draft.lines.value.length === 1 ? "item" : "different items" }}
					</p>
					<Button
						size="sm"
						variant="subtle"
						theme="red"
						icon-left="lucide-trash-2"
						label="Clear cart"
						:disabled="!!draft.busy.value"
						:loading="draft.busy.value === 'clear'"
						@click="emit('clear')"
					/>
				</div>

				<ul v-if="draft.lines.value.length" class="divide-y divide-outline-gray-1">
					<li
						v-for="line in draft.lines.value"
						:key="`${line.item_code}::${line.uom}`"
						class="flex flex-col gap-2 py-3 first:pt-0"
					>
						<div class="flex items-start justify-between gap-3">
							<p class="min-w-0 text-base font-medium leading-snug text-ink-gray-9">
								{{ line.item_name }}
							</p>
							<p
								class="shrink-0 whitespace-nowrap text-base font-semibold tabular-nums text-ink-gray-9"
							>
								<template v-if="draft.pricedLine(line)">
									{{
										money(draft.pricedLine(line)!.amount, draft.currency.value)
									}}
								</template>
								<span
									v-else
									class="inline-block h-3.5 w-16 animate-pulse rounded bg-surface-gray-2"
								/>
							</p>
						</div>
						<div class="flex items-center justify-between gap-3">
							<div class="flex min-w-0 items-center gap-2 text-p-sm text-ink-gray-6">
								<Select
									v-if="line.uoms.length > 1"
									size="sm"
									class="w-28"
									:aria-label="`Unit for ${line.item_name}`"
									:options="
										line.uoms.map((option) => ({
											label: option.uom,
											value: option.uom,
										}))
									"
									:model-value="line.uom"
									@update:model-value="draft.changeUom(line, String($event))"
								/>
								<span v-else>{{ line.uom }}</span>
								<span v-if="draft.pricedLine(line)" class="truncate tabular-nums">
									×
									{{ money(draft.pricedLine(line)!.rate, draft.currency.value) }}
								</span>
							</div>
							<QtyStepper
								class="w-32 shrink-0"
								size="sm"
								:model-value="line.qty"
								:label="line.item_name"
								@update:model-value="draft.setQty(line, $event)"
							/>
						</div>
					</li>
				</ul>
			</section>

			<section class="flex flex-col gap-4 border-t pt-4" aria-label="Delivery">
				<FormControl
					v-model="draft.deliveryDate.value"
					type="date"
					label="Deliver by"
					:min="draft.form.value?.today"
					required
				/>

				<fieldset v-if="draft.addresses.value.length > 1">
					<legend class="mb-1.5 text-xs text-ink-gray-5">
						Deliver to <span class="text-ink-red-4">*</span>
					</legend>
					<div class="flex flex-col gap-2">
						<label
							v-for="option in draft.addresses.value"
							:key="option.name"
							class="address-option flex cursor-pointer items-start gap-2.5 rounded-6 border p-3 transition-[background-color,border-color,box-shadow]"
							:class="
								draft.address.value === option.name
									? 'border-outline-gray-7 bg-surface-gray-1 shadow-[0_0_0_1px_var(--outline-gray-7)]'
									: 'border-outline-gray-2 bg-surface-base hover:border-outline-gray-4'
							"
						>
							<input
								v-model="draft.address.value"
								type="radio"
								name="delivery-address"
								class="sr-only"
								:value="option.name"
							/>
							<span
								class="mt-0.5 grid size-4 shrink-0 place-items-center rounded-full border-[1.5px] transition-colors"
								:class="
									draft.address.value === option.name
										? 'border-outline-gray-9 bg-surface-gray-10'
										: 'border-outline-gray-4 bg-surface-base'
								"
								aria-hidden="true"
							>
								<span
									v-if="draft.address.value === option.name"
									class="size-1.5 rounded-full bg-surface-base"
								/>
							</span>
							<span class="min-w-0 flex-1">
								<span class="flex items-center justify-between gap-2">
									<span
										class="truncate text-base font-medium"
										:class="
											draft.address.value === option.name
												? 'text-ink-gray-9'
												: 'text-ink-gray-8'
										"
									>
										{{ option.title }}
									</span>
									<span
										v-if="draft.address.value === option.name"
										class="shrink-0 rounded-full bg-surface-gray-10 px-2 py-0.5 text-xs font-semibold text-ink-base"
									>
										Selected
									</span>
								</span>
								<span class="block text-p-sm text-ink-gray-6">
									{{ option.lines || "No address lines on file" }}
								</span>
							</span>
						</label>
					</div>
				</fieldset>
				<div v-else-if="draft.addresses.value.length === 1" class="text-p-sm">
					<p class="text-xs text-ink-gray-5">Deliver to</p>
					<p class="mt-1 text-ink-gray-8">
						{{ draft.addresses.value[0]!.title }}
						<span class="text-ink-gray-5"
							>· {{ draft.addresses.value[0]!.lines }}</span
						>
					</p>
				</div>
				<p v-else class="text-p-sm text-ink-gray-5">
					We do not have a delivery address for you yet. Our team will confirm where to
					deliver.
				</p>

				<FormControl
					v-model="draft.poNo.value"
					type="text"
					label="Your reference (optional)"
					placeholder="e.g. your PO number"
					maxlength="140"
				/>
			</section>

			<p class="text-p-xs text-ink-gray-5">
				Prices come from your account's price list. We confirm every order before it is
				processed.
			</p>
		</div>

		<div
			class="cart-footer sticky bottom-0 flex shrink-0 flex-col gap-3 border-t bg-surface-base pt-3"
		>
			<div class="flex flex-col gap-1.5 text-p-sm tabular-nums" aria-live="polite">
				<div class="flex justify-between gap-4 text-ink-gray-6">
					<span>Subtotal</span>
					<span>
						{{
							draft.priced.value && draft.lines.value.length
								? money(draft.priced.value.net_total, draft.currency.value)
								: "—"
						}}
					</span>
				</div>
				<div
					v-if="draft.priced.value?.total_taxes"
					class="flex justify-between gap-4 text-ink-gray-6"
				>
					<span>Taxes</span>
					<span>{{ money(draft.priced.value.total_taxes, draft.currency.value) }}</span>
				</div>
				<div
					class="flex items-center justify-between gap-4 text-lg font-semibold text-ink-gray-9"
				>
					<span>Total</span>
					<span class="flex items-center gap-2">
						<Spinner v-if="draft.pricing.value" class="size-3.5" />
						{{ total }}
					</span>
				</div>
			</div>

			<ErrorMessage v-if="draft.pricingError.value" :message="draft.pricingError.value" />
			<ErrorMessage v-if="draft.errorMessage.value" :message="draft.errorMessage.value" />

			<Button
				variant="solid"
				size="lg"
				icon-left="lucide-send"
				label="Send order"
				:disabled="!draft.ready.value || !!draft.pricingError.value"
				:loading="draft.busy.value === 'send'"
				@click="emit('send')"
			/>
			<p
				v-if="nextStep"
				class="flex items-center justify-center gap-1.5 text-p-xs font-medium text-ink-amber-7"
			>
				<i class="lucide-info size-3.5" aria-hidden="true" />
				To send: {{ nextStep.charAt(0).toLowerCase() + nextStep.slice(1) }}.
			</p>
			<Button
				variant="outline"
				:label="draft.dirty.value || !draft.orderName.value ? 'Save for later' : 'Saved'"
				:icon-left="
					draft.dirty.value || !draft.orderName.value
						? 'lucide-bookmark'
						: 'lucide-check'
				"
				:disabled="!draft.ready.value || (!!draft.orderName.value && !draft.dirty.value)"
				:loading="draft.busy.value === 'draft'"
				@click="emit('save')"
			/>
		</div>
	</div>
</template>

<style scoped>
.address-option:has(input:focus-visible) {
	outline: var(--focus-outline-default);
	outline-offset: 2px;
}

.cart-body {
	scrollbar-width: thin;
}
</style>
