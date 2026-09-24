import { createResource } from "frappe-ui";
import type { BadgeTheme } from "@/data/application";

export interface PurchasePage<Row> {
  rows: Row[];
  total: number;
  start: number;
  limit: number;
  counts: Record<string, number>;
}

export interface PurchaseOrderRow {
  name: string;
  supplier: string;
  transaction_date: string;
  required_by: string | null;
  currency: string | null;
  grand_total: number | null;
  received: number;
  billed: number;
  status: string;
}

export interface PurchaseInvoiceRow {
  name: string;
  supplier: string;
  posting_date: string;
  due_date: string | null;
  bill_no: string | null;
  currency: string | null;
  grand_total: number | null;
  outstanding_amount: number | null;
  status: string;
}

export const PURCHASE_ORDER_STATUS_THEME: Record<string, BadgeTheme> = {
  "To Receive and Bill": "blue",
  "To Receive": "blue",
  "To Bill": "amber",
  Completed: "green",
  Delivered: "green",
  "On Hold": "amber",
  Closed: "gray",
  Cancelled: "red",
};

export const PURCHASE_INVOICE_STATUS_THEME: Record<string, BadgeTheme> = {
  Unpaid: "amber",
  Overdue: "red",
  "Partly Paid": "amber",
  Paid: "green",
  Submitted: "blue",
  Return: "gray",
  "Debit Note Issued": "gray",
  Cancelled: "red",
  "Internal Transfer": "gray",
};

export const purchaseOrderList = createResource({
  url: "vuna_sourcing.api.transactions.supplier.get_purchase_orders",
  auto: false,
});

export const purchaseInvoiceList = createResource({
  url: "vuna_sourcing.api.transactions.supplier.get_purchase_invoices",
  auto: false,
});

export function money(
  value: number | null | undefined,
  currency?: string | null
) {
  if (value === null || value === undefined) return "—";
  const amount = value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return currency ? `${currency} ${amount}` : amount;
}

export function shortDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export interface PurchaseOrderItem {
  name: string;
  item_code: string;
  item_name: string;
  description: string | null;
  qty: number;
  uom: string | null;
  rate: number | null;
  amount: number | null;
  received_qty: number;
  outstanding_qty: number;
  required_by: string | null;
}

export interface PurchaseOrder {
  name: string;
  supplier: string;
  status: string;
  transaction_date: string;
  required_by: string | null;
  currency: string | null;
  total: number | null;
  grand_total: number | null;
  received: number;
  billed: number;
  terms: string | null;
  items: PurchaseOrderItem[];
  receipts: { name: string; posting_date: string; status: string }[];
}

export interface PurchaseInvoiceItem {
  name: string;
  item_code: string;
  item_name: string;
  description: string | null;
  qty: number;
  uom: string | null;
  rate: number | null;
  amount: number | null;
  purchase_order: string | null;
}

export interface PurchaseInvoice {
  name: string;
  supplier: string;
  status: string;
  bill_no: string | null;
  bill_date: string | null;
  posting_date: string;
  due_date: string | null;
  currency: string | null;
  total: number | null;
  grand_total: number | null;
  outstanding_amount: number | null;
  on_hold: boolean;
  hold_reason: string | null;
  release_date: string | null;
  terms: string | null;
  purchase_orders: string[];
  items: PurchaseInvoiceItem[];
  payments: {
    name: string;
    posting_date: string;
    mode_of_payment: string | null;
    reference_no: string | null;
    allocated_amount: number | null;
  }[];
}

export function createPurchaseOrderResource() {
  return createResource({
    url: "vuna_sourcing.api.transactions.supplier.get_purchase_order",
    auto: false,
  });
}

export function createPurchaseInvoiceResource() {
  return createResource({
    url: "vuna_sourcing.api.transactions.supplier.get_purchase_invoice",
    auto: false,
  });
}
