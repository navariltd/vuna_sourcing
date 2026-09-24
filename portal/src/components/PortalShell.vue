<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	Avatar,
	BottomSheet,
	Button,
	DesktopShell,
	Dropdown,
	MobileNav,
	MobileNavItem,
	MobileShell,
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarRail,
	SidebarRailItem,
	SidebarSection,
} from "frappe-ui";
import { useIsMobile } from "@/composables/useViewport";
import { usePartySwitch } from "@/composables/usePartySwitch";
import { partyKey, usePortalStore } from "@/stores/portal";
import type { Party } from "@/stores/portal";
import { session } from "@/data/session";
import PartySwitcher from "@/components/PartySwitcher.vue";
import PortalSettings from "@/components/PortalSettings.vue";

const portal = usePortalStore();
const route = useRoute();
const router = useRouter();
const { setActiveParty } = usePartySwitch();

const showRail = computed(() => portal.parties.length > 1);

const activeKey = computed(() => (portal.activeParty ? partyKey(portal.activeParty) : null));

const headerTitle = computed(() =>
	portal.isMultiParty ? "Sourcing Portal" : portal.activeParty?.title ?? "Sourcing Portal"
);

const headerSubtitle = computed(() => {
	if (portal.isMultiParty) return portal.user?.full_name;
	if (portal.activeParty) return portal.activeParty.party_type;
	return portal.isApplicant ? "Application in progress" : portal.user?.full_name;
});

const userMenu = computed(() => [
	{
		label: "Settings",
		icon: "lucide-settings",
		onClick: () => (settingsOpen.value = true),
	},
	{
		label: "Frappe Desk",
		icon: "lucide-layout-grid",
		onClick: () => {
			window.location.href = "/app";
		},
		condition: () => !portal.user?.is_website_user,
	},
	{
		label: "Sign out",
		icon: "lucide-log-out",
		onClick: () => session.logout.submit(),
	},
]);

function switchParty(party: Party) {
	setActiveParty(party);
}

const isMobile = useIsMobile();

const accountSheet = ref(false);
const settingsOpen = ref(false);

const canApply = computed(() => portal.canApply && portal.partyTypesToJoin.length > 0);

const isSupplier = computed(() => portal.activeParty?.party_type === "Supplier");
const isCustomer = computed(() => portal.activeParty?.party_type === "Customer");

interface NavLink {
	label: string;
	icon: string;
	route: string;
	tab?: string;
}

interface NavSection {
	label: string;
	links: NavLink[];
	collapsible: boolean;
}

const BUYING: NavLink[] = [
	{ label: "Request for Quotation", icon: "lucide-file-text", route: "RfqList", tab: "RFQs" },
	{ label: "Supplier Quotations", icon: "lucide-file-check", route: "SupplierQuotationList" },
	{
		label: "Purchase Orders",
		icon: "lucide-package",
		route: "PurchaseOrderList",
		tab: "Orders",
	},
	{ label: "Purchase Invoices", icon: "lucide-receipt", route: "PurchaseInvoiceList" },
	{ label: "Debit Notes", icon: "lucide-receipt-cent", route: "DebitNoteList" },
];

const SELLING: NavLink[] = [
	{ label: "Quotations", icon: "lucide-file-badge", route: "QuotationList" },
	{
		label: "Sales Orders",
		icon: "lucide-shopping-cart",
		route: "SalesOrderList",
		tab: "Orders",
	},
	{ label: "Delivery Notes", icon: "lucide-truck", route: "DeliveryNoteList" },
	{
		label: "Sales Invoices",
		icon: "lucide-receipt-text",
		route: "SalesInvoiceList",
		tab: "Invoices",
	},
	{ label: "Credit Notes", icon: "lucide-receipt-cent", route: "CreditNoteList" },
];

const navSections = computed<NavSection[]>(() => {
	const sections: NavSection[] = [];
	if (portal.suppliers.length)
		sections.push({ label: "Buying", links: BUYING, collapsible: true });
	if (portal.customers.length)
		sections.push({ label: "Selling", links: SELLING, collapsible: true });
	sections.push({
		label: "Onboarding",
		collapsible: false,
		links: [
			...(portal.canApply
				? [{ label: "Onboard", icon: "lucide-file-pen-line", route: "ApplicationForm" }]
				: []),
			{ label: "My applications", icon: "lucide-folder-clock", route: "ApplicationList" },
		],
	});
	return sections;
});

const tabs = computed(() => {
	const side = isSupplier.value ? BUYING : isCustomer.value ? SELLING : [];
	return side.filter((link) => link.tab);
});

const moreSheet = ref(false);

const moreActive = computed(
	() =>
		moreSheet.value ||
		(route.name !== "PortalOverview" &&
			!tabs.value.some((link) => link.route === route.name) &&
			navSections.value.some((section) =>
				section.links.some((link) => link.route === route.name)
			))
);

function goTo(link: NavLink) {
	moreSheet.value = false;
	router.push({ name: link.route });
}

const accountActions = computed(() =>
	userMenu.value.filter((item) => !item.condition || item.condition())
);

function runAccountAction(action: () => void) {
	accountSheet.value = false;
	action();
}
</script>

<template>
	<MobileShell v-if="isMobile">
		<PartySwitcher
			class="sticky top-0 z-10 border-b border-outline-gray-2 bg-surface-white px-4 py-2"
		/>

		<RouterView :key="route.fullPath" />

		<template #nav>
			<MobileNav>
				<MobileNavItem
					v-if="portal.hasParties"
					label="Overview"
					icon="lucide-layout-dashboard"
					:route="{ name: 'PortalOverview' }"
				/>
				<MobileNavItem
					v-for="link in tabs"
					:key="link.route"
					:label="link.tab!"
					:icon="link.icon"
					:route="{ name: link.route }"
				/>
				<MobileNavItem
					v-if="isSupplier || isCustomer"
					label="More"
					icon="lucide-layout-list"
					:active="moreActive"
					@click="moreSheet = true"
				/>
				<MobileNavItem
					v-if="!isSupplier && !isCustomer"
					label="Applications"
					icon="lucide-folder-clock"
					:route="{ name: 'ApplicationList' }"
				/>
				<MobileNavItem
					v-if="!isSupplier && !isCustomer && canApply"
					label="Apply"
					icon="lucide-file-pen-line"
					:route="{ name: 'ApplicationForm' }"
				/>
				<MobileNavItem label="You" :active="accountSheet" @click="accountSheet = true">
					<Avatar
						:image="portal.user?.image || undefined"
						:label="portal.user?.full_name || '?'"
						size="sm"
					/>
				</MobileNavItem>
			</MobileNav>
		</template>
	</MobileShell>

	<DesktopShell v-else>
		<template v-if="showRail" #rail>
			<SidebarRail class="gap-2 !bg-surface-gray-4">
				<SidebarRailItem
					v-for="party in portal.parties"
					:key="partyKey(party)"
					:label="party.title"
					:description="party.party_type"
					:active="partyKey(party) === activeKey"
					@click="switchParty(party)"
				>
					<Avatar
						:image="party.image || undefined"
						:label="party.title"
						size="lg"
						shape="square"
					/>
				</SidebarRailItem>

				<div class="mt-auto flex flex-col items-center gap-2 pb-1">
					<SidebarRailItem
						v-if="portal.canApply"
						label="Onboard"
						description="Apply as a supplier or customer"
						icon="lucide-plus"
						variant="ghost"
						:route="{ name: 'ApplicationForm' }"
					/>
					<SidebarRailItem
						label="Settings"
						description="Profile and preferences"
						icon="lucide-settings"
						variant="ghost"
						@click="settingsOpen = true"
					/>
				</div>
			</SidebarRail>
		</template>

		<template #sidebar>
			<Sidebar>
				<SidebarHeader
					:title="headerTitle"
					:subtitle="headerSubtitle || undefined"
					:show-logo="!showRail"
					:menu-items="[
						{
							label: 'Settings',
							icon: 'lucide-settings',
							onClick: () => (settingsOpen = true),
						},
					]"
				>
					<template v-if="!showRail" #prefix>
						<Avatar
							:image="portal.activeParty?.image || undefined"
							:label="headerTitle"
							size="md"
							shape="square"
						/>
					</template>
				</SidebarHeader>

				<PartySwitcher class="px-2 pb-1" />

				<div class="flex-1 overflow-y-auto px-2 py-1">
					<SidebarItem
						v-if="portal.hasParties"
						label="Overview"
						icon="lucide-layout-dashboard"
						:route="{ name: 'PortalOverview' }"
					/>

					<SidebarSection
						v-for="section in navSections"
						:key="section.label"
						:label="section.label"
						:collapsible="section.collapsible"
					>
						<SidebarItem
							v-for="link in section.links"
							:key="link.route"
							:label="link.label"
							:icon="link.icon"
							:route="{ name: link.route }"
						/>
					</SidebarSection>
				</div>

				<div class="border-t p-2">
					<Dropdown :options="userMenu" placement="top-start" class="w-full">
						<button
							class="flex w-full items-center gap-2 rounded-4 p-1 text-left hover:bg-surface-gray-2"
						>
							<Avatar
								:image="portal.user?.image || undefined"
								:label="portal.user?.full_name || '?'"
								size="md"
							/>
							<span class="min-w-0 flex-1">
								<span class="block truncate text-base font-medium text-ink-gray-8">
									{{ portal.user?.full_name }}
								</span>
								<span class="block truncate text-xs text-ink-gray-5">
									{{ portal.user?.email }}
								</span>
							</span>
							<i class="lucide-chevrons-up-down size-4 shrink-0 text-ink-gray-5" />
						</button>
					</Dropdown>
				</div>
			</Sidebar>
		</template>

		<RouterView :key="route.fullPath" />
	</DesktopShell>

	<BottomSheet v-if="isMobile" v-model:open="accountSheet" title="Account">
		<div class="px-4 pb-6">
			<div class="flex items-center gap-3">
				<Avatar
					:image="portal.user?.image || undefined"
					:label="portal.user?.full_name || '?'"
					size="lg"
				/>
				<div class="min-w-0">
					<p class="truncate text-base font-medium text-ink-gray-8">
						{{ portal.user?.full_name }}
					</p>
					<p class="truncate text-sm text-ink-gray-5">{{ portal.user?.email }}</p>
				</div>
			</div>

			<div class="mt-4 flex flex-col gap-2">
				<Button
					v-for="action in accountActions"
					:key="action.label"
					:label="action.label"
					:icon-left="action.icon"
					size="md"
					@click="runAccountAction(action.onClick)"
				/>
			</div>
		</div>
	</BottomSheet>

	<BottomSheet v-if="isMobile" v-model:open="moreSheet" title="All transactions">
		<div class="space-y-4 px-4 pb-6">
			<section v-for="section in navSections" :key="section.label">
				<p class="px-1 pb-1 text-xs uppercase tracking-wide text-ink-gray-5">
					{{ section.label }}
				</p>
				<div class="flex flex-col">
					<button
						v-for="link in section.links"
						:key="link.route"
						type="button"
						class="flex items-center gap-3 rounded-4 px-2 py-2.5 text-left text-base"
						:class="
							route.name === link.route
								? 'bg-surface-gray-2 font-medium text-ink-gray-9'
								: 'text-ink-gray-8 active:bg-surface-gray-2'
						"
						@click="goTo(link)"
					>
						<i :class="[link.icon, 'size-4 shrink-0 text-ink-gray-6']" />
						<span class="flex-1">{{ link.label }}</span>
						<i class="lucide-chevron-right size-4 text-ink-gray-4" />
					</button>
				</div>
			</section>
		</div>
	</BottomSheet>

	<PortalSettings v-model:open="settingsOpen" />
</template>
