<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
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
	useKeyboardShortcut,
} from "frappe-ui";
import { useIsMobile } from "@/composables/useViewport";
import { usePartySwitch } from "@/composables/usePartySwitch";
import { ACCENTS, LOOKS } from "@/data/accents";
import type { DocumentLook } from "@/data/accents";
import { partyKey, usePortalStore } from "@/stores/portal";
import type { Party } from "@/stores/portal";
import { session } from "@/data/session";
import PartySwitcher from "@/components/PartySwitcher.vue";
import BranchFilter from "@/components/BranchFilter.vue";
import PortalSettings from "@/components/PortalSettings.vue";
import LiveBidDock from "@/components/LiveBidDock.vue";
import PortalSearch from "@/components/PortalSearch.vue";
import { appsFor, installedApps } from "@/data/apps";
import type { InstalledApp } from "@/data/apps";
import type { SearchPageLink } from "@/components/PortalSearch.vue";

const portal = usePortalStore();
const route = useRoute();
const router = useRouter();
const { setActiveParty } = usePartySwitch();

const showRail = computed(() => portal.parties.length > 1);

const activeKey = computed(() => (portal.activeParty ? partyKey(portal.activeParty) : null));

const portalTitle = computed(() => portal.branding.title || "Sourcing Portal");

const headerTitle = computed(() =>
	portal.isMultiParty ? portalTitle.value : portal.activeParty?.title ?? portalTitle.value
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
		label: "Sign out",
		icon: "lucide-log-out",
		onClick: () => session.logout.submit(),
	},
]);

onMounted(() => {
	if (!installedApps.data) installedApps.fetch();
});

const apps = computed(() => appsFor(portal.user?.is_website_user !== false));

function openApp(app: InstalledApp) {
	window.location.href = app.route;
}

function appIcon(app: InstalledApp) {
	if (!app.logo) return "lucide-app-window";
	const logo = app.logo;
	return () => h("img", { src: logo, alt: "", class: "size-4 rounded-[3px] object-contain" });
}

const headerMenu = computed(() => [
	...(apps.value.length
		? [
				{
					label: "Apps",
					icon: "lucide-layout-grid",
					submenu: apps.value.map((app) => ({
						label: app.title,
						icon: appIcon(app),
						onClick: () => openApp(app),
					})),
				},
		  ]
		: []),
	{
		label: "Settings",
		icon: "lucide-settings",
		onClick: () => (settingsOpen.value = true),
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
	look: DocumentLook;
	route: string;
	tab?: string;
}

interface NavSection {
	label: string;
	links: NavLink[];
	collapsible: boolean;
}

const BUYING: NavLink[] = [
	{ label: "Request for Quotation", look: LOOKS.rfq, route: "RfqList", tab: "RFQs" },
	{
		label: "Supplier Quotation",
		look: LOOKS.supplierQuotation,
		route: "SupplierQuotationList",
	},
	{
		label: "Purchase Order",
		look: LOOKS.purchaseOrder,
		route: "PurchaseOrderList",
		tab: "Orders",
	},
	{ label: "Purchase Invoice", look: LOOKS.purchaseInvoice, route: "PurchaseInvoiceList" },
	{ label: "Debit Note", look: LOOKS.debitNote, route: "DebitNoteList" },
	{ label: "Pending Invoices", look: LOOKS.payable, route: "SupplierStatement" },
];

const SELLING: NavLink[] = [
	{ label: "Quotation", look: LOOKS.quotation, route: "QuotationList" },
	{ label: "Sales Order", look: LOOKS.salesOrder, route: "SalesOrderList", tab: "Orders" },
	{ label: "Delivery Note", look: LOOKS.deliveryNote, route: "DeliveryNoteList" },
	{
		label: "Sales Invoice",
		look: LOOKS.salesInvoice,
		route: "SalesInvoiceList",
		tab: "Invoices",
	},
	{ label: "Credit Note", look: LOOKS.creditNote, route: "CreditNoteList" },
	{ label: "Credit Note Request", look: LOOKS.creditRequest, route: "CreditRequestList" },
	{ label: "Pending Invoices", look: LOOKS.receivable, route: "CustomerStatement" },
];

const sellingLinks = computed(() =>
	SELLING.filter((link) => link.route !== "CreditRequestList" || portal.features.credit_requests)
);

const navSections = computed<NavSection[]>(() => {
	const sections: NavSection[] = [];
	if (portal.suppliers.length)
		sections.push({ label: "Buying", links: BUYING, collapsible: true });
	if (portal.customers.length)
		sections.push({ label: "Selling", links: sellingLinks.value, collapsible: true });
	sections.push({
		label: "Onboarding",
		collapsible: false,
		links: [
			...(portal.canApply
				? [{ label: "Onboard", look: LOOKS.onboard, route: "ApplicationForm" }]
				: []),
			{ label: "My applications", look: LOOKS.application, route: "ApplicationList" },
		],
	});
	return sections;
});

const tabs = computed(() => {
	const side = isSupplier.value ? BUYING : isCustomer.value ? sellingLinks.value : [];
	return side.filter((link) => link.tab);
});

const moreSheet = ref(false);

const searchOpen = ref(false);

function openSearch() {
	searchOpen.value = true;
}

useKeyboardShortcut([
	{ combo: "Mod+K", description: "Search the portal", allowInInput: true, handler: openSearch },
	{ combo: "Ctrl+K", description: "Search the portal", allowInInput: true, handler: openSearch },
]);

const searchPages = computed<SearchPageLink[]>(() => {
	const side = isSupplier.value ? BUYING : isCustomer.value ? sellingLinks.value : [];
	return [
		...(portal.hasParties
			? [{ label: "Overview", route: "PortalOverview", look: LOOKS.application }]
			: []),
		...(isCustomer.value && portal.features.customer_orders
			? [{ label: "New order", route: "SalesOrderNew", look: LOOKS.salesOrder }]
			: []),
		...side.map((link) => ({ label: link.label, route: link.route, look: link.look })),
		{ label: "My applications", route: "ApplicationList", look: LOOKS.application },
	];
});

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

const accountActions = userMenu;

function runAccountAction(action: () => void) {
	accountSheet.value = false;
	action();
}
</script>

<template>
	<MobileShell v-if="isMobile">
		<div class="sticky top-0 z-30 bg-surface-base shadow-sm">
			<div class="flex items-center gap-2 border-b border-outline-gray-2 py-2 pl-4 pr-2">
				<PartySwitcher v-if="portal.isMultiParty" class="min-w-0 flex-1" />
				<div v-else class="flex min-w-0 flex-1 items-center gap-2">
					<Avatar
						:image="portal.activeParty?.image || undefined"
						:label="headerTitle"
						size="md"
						shape="square"
					/>
					<span class="min-w-0">
						<span class="block truncate text-base font-semibold text-ink-gray-9">
							{{ headerTitle }}
						</span>
						<span
							v-if="headerSubtitle"
							class="block truncate text-p-xs text-ink-gray-5"
						>
							{{ headerSubtitle }}
						</span>
					</span>
				</div>
				<Button
					v-if="portal.hasParties"
					variant="ghost"
					size="md"
					icon="lucide-search"
					aria-label="Search"
					@click="searchOpen = true"
				/>
			</div>
			<BranchFilter class="border-b border-outline-gray-2 px-4 py-2" />
		</div>

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
					:icon="link.look.icon"
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
					:menu-items="headerMenu"
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
				<BranchFilter class="px-2 pb-1" />

				<div v-if="portal.hasParties" class="px-2 pb-1">
					<button
						type="button"
						class="flex h-8 w-full items-center gap-2 rounded-6 border border-outline-gray-2 bg-surface-base px-2 text-left text-base text-ink-gray-5 transition-colors hover:border-outline-gray-3 hover:text-ink-gray-7 focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-4"
						aria-label="Search the portal"
						@click="searchOpen = true"
					>
						<i class="lucide-search size-4 shrink-0" aria-hidden="true" />
						<span class="flex-1 truncate">Search</span>
						<kbd
							class="shrink-0 rounded-4 border border-outline-gray-2 bg-surface-gray-1 px-1 py-px font-sans text-[11px] leading-4 text-ink-gray-5"
							aria-label="Command or Control plus K"
						>
							⌘/Ctrl K
						</kbd>
					</button>
				</div>

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
							:route="{ name: link.route }"
						>
							<template #prefix>
								<i
									:class="[
										link.look.icon,
										ACCENTS[link.look.accent].icon,
										'size-4',
									]"
									aria-hidden="true"
								/>
							</template>
						</SidebarItem>
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

			<section v-if="apps.length" class="mt-4" aria-label="Apps">
				<p class="px-1 pb-1 text-xs uppercase tracking-wide text-ink-gray-5">Apps</p>
				<div class="grid grid-cols-3 gap-2">
					<a
						v-for="app in apps"
						:key="app.name + app.route"
						:href="app.route"
						class="flex flex-col items-center gap-1.5 rounded-8 border border-outline-gray-2 p-3 text-center active:bg-surface-gray-2"
					>
						<img
							v-if="app.logo"
							:src="app.logo"
							alt=""
							class="size-8 rounded-6 object-contain"
						/>
						<i
							v-else
							class="lucide-app-window size-8 text-ink-gray-6"
							aria-hidden="true"
						/>
						<span class="w-full truncate text-p-sm text-ink-gray-8">{{
							app.title
						}}</span>
					</a>
				</div>
			</section>

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
						<span
							class="grid size-7 shrink-0 place-items-center rounded-5"
							:class="ACCENTS[link.look.accent].tile"
						>
							<i :class="[link.look.icon, 'size-4']" aria-hidden="true" />
						</span>
						<span class="flex-1">{{ link.label }}</span>
						<i class="lucide-chevron-right size-4 text-ink-gray-4" />
					</button>
				</div>
			</section>
		</div>
	</BottomSheet>

	<PortalSettings v-model:open="settingsOpen" />
	<PortalSearch v-if="portal.hasParties" v-model:open="searchOpen" :pages="searchPages" />
	<LiveBidDock />
</template>
