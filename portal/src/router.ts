import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { session } from '@/data/session'
import { usePortalStore } from '@/stores/portal'

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
  },
  {
    path: '/rfq/:name',
    name: 'RfqDetail',
    component: () => import('@/pages/RfqDetail.vue'),
    props: true,
  },
  {
    path: '/supplier-quotations',
    name: 'SupplierQuotationList',
    component: () => import('@/pages/SupplierQuotationList.vue'),
  },
  {
    path: '/supplier-quotations/:name',
    name: 'SupplierQuotationDetail',
    component: () => import('@/pages/SupplierQuotationDetail.vue'),
    props: true,
  },
  {
    path: '/purchase-orders',
    name: 'PurchaseOrderList',
    component: () => import('@/pages/PurchaseOrderList.vue'),
  },
  {
    path: '/purchase-orders/:name',
    name: 'PurchaseOrderDetail',
    component: () => import('@/pages/PurchaseOrderDetail.vue'),
    props: true,
  },
  {
    path: '/purchase-invoices',
    name: 'PurchaseInvoiceList',
    component: () => import('@/pages/PurchaseInvoiceList.vue'),
  },
  {
    path: '/purchase-invoices/:name',
    name: 'PurchaseInvoiceDetail',
    component: () => import('@/pages/PurchaseInvoiceDetail.vue'),
    props: true,
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

  return true
})
