import { createResource } from "frappe-ui";
import type { BadgeTheme } from "@/data/application";
import type { ReturnNote } from "@/data/purchase";
import type { InvoiceCreditState } from "@/data/creditRequests";

export interface QuotationRow {
  name: string;
  customer: string;
  transaction_date: string;
  valid_till: string | null;
  currency: string | null;
  grand_total: number | null;
  branch?: string | null;
  status: string;
}

export interface SalesOrderRow {
  name: string;
  customer: string;
  po_no: string | null;
  transaction_date: string;
  delivery_date: string | null;
  currency: string | null;
  grand_total: number | null;
  delivered: number;
  billed: number;
  branch?: string | null;
  status: string;
  is_draft: boolean;
}

export interface DeliveryNoteRow {
  name: string;
  customer: string;
  po_no: string | null;
  posting_date: string;
  lr_no: string | null;
  transporter_name: string | null;
  currency: string | null;
  grand_total: number | null;
  is_return: boolean;
  branch?: string | null;
  status: string;
}

export interface SalesInvoiceRow {
  name: string;
  customer: string;
  po_no: string | null;
  posting_date: string;
  due_date: string | null;
  currency: string | null;
  grand_total: number | null;
  outstanding_amount: number | null;
  is_return: boolean;
  return_against: string | null;
  is_debit_note: boolean;
  branch?: string | null;
  status: string;
}

export const QUOTATION_STATUS_THEME: Record<string, BadgeTheme> = {
  Open: "blue",
  Replied: "blue",
  "Partially Ordered": "amber",
  Ordered: "green",
  Lost: "gray",
  Expired: "gray",
  Cancelled: "red",
};

export const SALES_ORDER_STATUS_THEME: Record<string, BadgeTheme> = {
  Draft: "gray",
  "Awaiting Confirmation": "violet",
  "To Deliver and Bill": "blue",
  "To Deliver": "blue",
  "To Bill": "amber",
  "To Pay": "amber",
  Completed: "green",
  "On Hold": "amber",
  Closed: "gray",
  Cancelled: "red",
};

export const DELIVERY_NOTE_STATUS_THEME: Record<string, BadgeTheme> = {
  "To Bill": "blue",
  "Partially Billed": "amber",
  Completed: "green",
  Return: "gray",
  "Return Issued": "gray",
  Closed: "gray",
  Cancelled: "red",
};

export const SALES_INVOICE_STATUS_THEME: Record<string, BadgeTheme> = {
  Unpaid: "amber",
  Overdue: "red",
  "Partly Paid": "amber",
  Paid: "green",
  Submitted: "blue",
  "Unpaid and Discounted": "amber",
  "Partly Paid and Discounted": "amber",
  "Overdue and Discounted": "red",
  Return: "gray",
  "Credit Note Issued": "gray",
  Cancelled: "red",
  "Internal Transfer": "gray",
};

export const quotationList = createResource({
  url: "vuna_sourcing.api.transactions.customer.get_quotations",
  auto: false,
});

export const salesOrderList = createResource({
  url: "vuna_sourcing.api.transactions.customer.get_sales_orders",
  auto: false,
});

export const deliveryNoteList = createResource({
  url: "vuna_sourcing.api.transactions.customer.get_delivery_notes",
  auto: false,
});

export const salesInvoiceList = createResource({
  url: "vuna_sourcing.api.transactions.customer.get_sales_invoices",
  auto: false,
});

export const creditNoteList = createResource({
  url: "vuna_sourcing.api.transactions.customer.get_sales_invoices",
  auto: false,
});

interface LineItem {
  name: string;
  item_code: string;
  item_name: string;
  description: string | null;
  qty: number;
  uom: string | null;
  rate: number | null;
  amount: number | null;
}

export interface Quotation {
  name: string;
  customer: string;
  branch?: string | null;
  status: string;
  transaction_date: string;
  valid_till: string | null;
  currency: string | null;
  total: number | null;
  total_taxes: number | null;
  grand_total: number | null;
  terms: string | null;
  items: LineItem[];
  sales_orders: string[];
}

export interface SalesOrderItem extends LineItem {
  delivered_qty: number;
  outstanding_qty: number;
  delivery_date: string | null;
  quotation: string | null;
}

export interface SalesOrder {
  name: string;
  customer: string;
  branch?: string | null;
  status: string;
  is_draft: boolean;
  editable: boolean;
  withdrawable: boolean;
  po_no: string | null;
  po_date: string | null;
  transaction_date: string;
  delivery_date: string | null;
  currency: string | null;
  total: number | null;
  grand_total: number | null;
  delivered: number;
  billed: number;
  shipping_address: string | null;
  terms: string | null;
  quotations: string[];
  items: SalesOrderItem[];
  deliveries: {
    name: string;
    posting_date: string;
    status: string;
    is_return: 0 | 1;
  }[];
  invoices: string[];
}

export interface DeliveryNoteItem extends LineItem {
  returned_qty: number;
  sales_order: string | null;
}

export interface DeliveryNote {
  name: string;
  customer: string;
  branch?: string | null;
  status: string;
  is_return: boolean;
  return_against: string | null;
  po_no: string | null;
  posting_date: string;
  currency: string | null;
  total: number | null;
  grand_total: number | null;
  billed: number;
  transporter_name: string | null;
  lr_no: string | null;
  lr_date: string | null;
  vehicle_no: string | null;
  driver_name: string | null;
  shipping_address: string | null;
  terms: string | null;
  sales_orders: string[];
  items: DeliveryNoteItem[];
  invoices: string[];
}

export interface SalesInvoiceItem extends LineItem {
  sales_order: string | null;
  delivery_note: string | null;
}

export interface SalesInvoice {
  name: string;
  customer: string;
  branch?: string | null;
  status: string;
  is_return: boolean;
  is_debit_note: boolean;
  return_against: string | null;
  po_no: string | null;
  posting_date: string;
  due_date: string | null;
  currency: string | null;
  total: number | null;
  total_taxes: number | null;
  grand_total: number | null;
  outstanding_amount: number | null;
  terms: string | null;
  sales_orders: string[];
  delivery_notes: string[];
  items: SalesInvoiceItem[];
  payments: {
    name: string;
    posting_date: string;
    mode_of_payment: string | null;
    reference_no: string | null;
    allocated_amount: number | null;
  }[];
  credit_notes: ReturnNote[];
  credit_request: InvoiceCreditState;
}

export function createQuotationResource() {
  return createResource({
    url: "vuna_sourcing.api.transactions.customer.get_quotation",
    auto: false,
  });
}

export function createSalesOrderResource() {
  return createResource({
    url: "vuna_sourcing.api.transactions.customer.get_sales_order",
    auto: false,
  });
}

export function createDeliveryNoteResource() {
  return createResource({
    url: "vuna_sourcing.api.transactions.customer.get_delivery_note",
    auto: false,
  });
}

export function createSalesInvoiceResource() {
  return createResource({
    url: "vuna_sourcing.api.transactions.customer.get_sales_invoice",
    auto: false,
  });
}
