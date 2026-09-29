import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { session } from '@/data/session'
import { usePortalStore } from '@/stores/portal'
import type { PartyType } from '@/stores/portal'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    partyType?: PartyType
  }
}

export const BASE_PATH = '/vuna-sourcing'

const routes: RouteRecordRaw[] = [
  {
    path: '/signup',
    name: 'Signup',
    component: () => import('@/pages/Signup.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'Home',
    redirect: { name: 'PortalOverview' },
  },
  {
    path: '/overview',
    name: 'PortalOverview',
    component: () => import('@/pages/PortalOverview.vue'),
  },
  {
    path: '/application',
    name: 'ApplicationForm',
    component: () => import('@/pages/ApplicationForm.vue'),
  },
  {
    path: '/rfq',
    name: 'RfqList',
    component: () => import('@/pages/RfqList.vue'),
    meta: { partyType: 'Supplier' },
  },
  {
    path: '/rfq/:name',
    name: 'RfqDetail',
    component: () => import('@/pages/RfqDetail.vue'),
    meta: { partyType: 'Supplier' },
    props: true,
  },
  {
    path: '/supplier-quotations',
    name: 'SupplierQuotationList',
    component: () => import('@/pages/SupplierQuotationList.vue'),
    meta: { partyType: 'Supplier' },
  },
  {
    path: '/supplier-quotations/:name',
    name: 'SupplierQuotationDetail',
    component: () => import('@/pages/SupplierQuotationDetail.vue'),
    meta: { partyType: 'Supplier' },
    props: true,
  },
  {
    path: '/purchase-orders',
    name: 'PurchaseOrderList',
    component: () => import('@/pages/PurchaseOrderList.vue'),
    meta: { partyType: 'Supplier' },
  },
  {
    path: '/purchase-orders/:name',
    name: 'PurchaseOrderDetail',
    component: () => import('@/pages/PurchaseOrderDetail.vue'),
    meta: { partyType: 'Supplier' },
    props: true,
  },
  {
    path: '/purchase-invoices',
    name: 'PurchaseInvoiceList',
    component: () => import('@/pages/PurchaseInvoiceList.vue'),
    meta: { partyType: 'Supplier' },
  },
  {
    path: '/debit-notes',
    name: 'DebitNoteList',
    component: () => import('@/pages/PurchaseInvoiceList.vue'),
    props: { debitNotes: true },
    meta: { partyType: 'Supplier' },
  },
  {
    path: '/purchase-invoices/:name',
    name: 'PurchaseInvoiceDetail',
    component: () => import('@/pages/PurchaseInvoiceDetail.vue'),
    meta: { partyType: 'Supplier' },
    props: true,
  },
  {
    path: '/quotations',
    name: 'QuotationList',
    component: () => import('@/pages/QuotationList.vue'),
    meta: { partyType: 'Customer' },
  },
  {
    path: '/quotations/:name',
    name: 'QuotationDetail',
    component: () => import('@/pages/QuotationDetail.vue'),
    props: true,
    meta: { partyType: 'Customer' },
  },
  {
    path: '/sales-orders',
    name: 'SalesOrderList',
    component: () => import('@/pages/SalesOrderList.vue'),
    meta: { partyType: 'Customer' },
  },
  {
    path: '/sales-orders/:name',
    name: 'SalesOrderDetail',
    component: () => import('@/pages/SalesOrderDetail.vue'),
    props: true,
    meta: { partyType: 'Customer' },
  },
  {
    path: '/delivery-notes',
    name: 'DeliveryNoteList',
    component: () => import('@/pages/DeliveryNoteList.vue'),
    meta: { partyType: 'Customer' },
  },
  {
    path: '/delivery-notes/:name',
    name: 'DeliveryNoteDetail',
    component: () => import('@/pages/DeliveryNoteDetail.vue'),
    props: true,
    meta: { partyType: 'Customer' },
  },
  {
    path: '/sales-invoices',
    name: 'SalesInvoiceList',
    component: () => import('@/pages/SalesInvoiceList.vue'),
    meta: { partyType: 'Customer' },
  },
  {
    path: '/credit-notes',
    name: 'CreditNoteList',
    component: () => import('@/pages/SalesInvoiceList.vue'),
    props: { creditNotes: true },
    meta: { partyType: 'Customer' },
  },
  {
    path: '/sales-invoices/:name',
    name: 'SalesInvoiceDetail',
    component: () => import('@/pages/SalesInvoiceDetail.vue'),
    props: true,
    meta: { partyType: 'Customer' },
  },
  {
    path: '/pending-purchase-invoices',
    name: 'SupplierStatement',
    component: () => import('@/pages/AccountStatement.vue'),
    props: { side: 'Supplier' },
    meta: { partyType: 'Supplier' },
  },
  {
    path: '/pending-sales-invoices',
    name: 'CustomerStatement',
    component: () => import('@/pages/AccountStatement.vue'),
    props: { side: 'Customer' },
    meta: { partyType: 'Customer' },
  },
  {
    path: '/applications',
    name: 'ApplicationList',
    component: () => import('@/pages/ApplicationList.vue'),
  },
  {
    path: '/applications/:name',
    name: 'ApplicationDetail',
    component: () => import('@/pages/ApplicationDetail.vue'),
    props: true,
  },
  { path: '/supplier-application', redirect: (to) => ({ name: 'ApplicationForm', query: to.query }) },
  { path: '/supplier-applications', redirect: { name: 'ApplicationList' } },
  {
    path: '/supplier-applications/:name',
    redirect: (to) => ({ name: 'ApplicationDetail', params: { name: to.params.name } }),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'PortalNotFound',
    component: () => import('@/pages/PortalNotFound.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(BASE_PATH),
  routes,
})

export function loginUrl(fullPath = '/') {
  return `/login?redirect-to=${encodeURIComponent(BASE_PATH + fullPath)}`
}

function redirectToLogin(fullPath: string) {
  window.location.href = loginUrl(fullPath)
}

router.beforeEach(async (to) => {
  if (to.meta.public) {
    return session.isLoggedIn ? { name: 'Home' } : true
  }

  if (!session.isLoggedIn) {
    redirectToLogin(to.fullPath)
    return false
  }

  const portal = usePortalStore()
  try {
    await portal.load()
  } catch {
    return true
  }

  if (portal.isApplicant && !portal.hasParties && to.name === 'PortalOverview') {
    return { name: 'ApplicationForm' }
  }

  const partyType = to.meta.partyType
  if (partyType) {
    if (!portal.partiesOfType(partyType).length) return { name: 'PortalOverview' }
    if (portal.activeParty?.party_type !== partyType) portal.switchToType(partyType)
  }

  return true
})
