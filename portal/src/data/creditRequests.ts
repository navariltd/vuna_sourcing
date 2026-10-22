import { createResource } from "frappe-ui";
import type { BadgeTheme } from "@/data/application";
import type { PurchasePage, ReturnNote } from "@/data/purchase";
import type { ApiResponse } from "@/types/api";

export type CreditRequestStatus =
  | "Pending Review"
  | "Returned for Correction"
  | "Approved"
  | "Rejected"
  | "Credit Note Issued"
  | "Withdrawn"
  | "Cancelled";

export const CREDIT_REQUEST_STATUS_THEME: Record<string, BadgeTheme> = {
  "Pending Review": "violet",
  "Returned for Correction": "amber",
  Approved: "blue",
  Rejected: "red",
  "Credit Note Issued": "green",
  Withdrawn: "gray",
  Cancelled: "red",
};

export const CREDIT_REQUEST_STATUS_LABEL: Record<string, string> = {
  "Pending Review": "Under review",
  "Returned for Correction": "Needs changes",
  Approved: "Approved",
  Rejected: "Declined",
  "Credit Note Issued": "Credited",
  Withdrawn: "Withdrawn",
  Cancelled: "Cancelled",
};

export function statusLabel(status: string | null) {
  return (status && CREDIT_REQUEST_STATUS_LABEL[status]) || status || "—";
}

export interface CreditRequestRow {
  name: string;
  sales_invoice: string;
  transaction_date: string;
  reason: string;
  currency: string | null;
  total_amount: number | null;
  status: CreditRequestStatus;
  credit_note: string | null;
}

export type CreditRequestPage = PurchasePage<CreditRequestRow> & { can_request: boolean };

export interface CreditRequestItem {
  sales_invoice_item: string;
  item_code: string;
  item_name: string;
  uom: string | null;
  rate: number;
  qty: number;
  amount: number;
}

export interface CreditRequest {
  name: string;
  customer: string;
  sales_invoice: string;
  status: CreditRequestStatus;
  transaction_date: string;
  reason: string;
  description: string | null;
  currency: string | null;
  total_qty: number;
  total_amount: number;
  review_remarks: string | null;
  reviewed_on: string | null;
  editable: boolean;
  withdrawable: boolean;
  credit_note: ReturnNote | null;
  items: CreditRequestItem[];
}

export interface CreditableInvoice {
  name: string;
  posting_date: string;
  po_no: string | null;
  currency: string | null;
  grand_total: number | null;
  open_request: string | null;
}

export interface CreditFormLine {
  sales_invoice_item: string;
  item_code: string;
  item_name: string;
  description: string | null;
  uom: string | null;
  rate: number;
  invoiced_qty: number;
  credited_qty: number;
  available_qty: number;
  qty: number;
}

export interface CreditForm {
  invoice: {
    name: string;
    posting_date: string;
    po_no: string | null;
    currency: string | null;
    total: number | null;
    total_taxes: number | null;
    grand_total: number | null;
  };
  reasons: string[];
  lines: CreditFormLine[];
  request: {
    name: string;
    reason: string;
    description: string | null;
    review_remarks: string | null;
  } | null;
}

export interface CreditRequestPayload {
  customer: string;
  items: { sales_invoice_item: string; qty: number }[];
  reason: string;
  description: string | null;
}

export interface InvoiceCreditState {
  can_request: boolean;
  open_request: { name: string; request_status: CreditRequestStatus } | null;
}

const CREDIT_REQUESTS = "vuna_sourcing.api.transactions.credit_requests";

export const creditRequestList = createResource({
  url: `${CREDIT_REQUESTS}.get_credit_requests`,
  auto: false,
});

export function createCreditRequestResource() {
  return createResource({
    url: `${CREDIT_REQUESTS}.get_credit_request`,
    auto: false,
  });
}

function post<T>(method: string, payload: object): Promise<ApiResponse<T>> {
  return createResource({ url: `${CREDIT_REQUESTS}.${method}`, method: "POST" }).submit(
    payload,
  );
}

export function fetchCreditableInvoices(
  customer: string,
  search?: string | null,
): Promise<ApiResponse<CreditableInvoice[]>> {
  return createResource({ url: `${CREDIT_REQUESTS}.get_creditable_invoices` }).fetch({
    customer,
    search: search || null,
  });
}

export function fetchCreditForm(params: {
  customer: string;
  sales_invoice?: string | null;
  name?: string | null;
}): Promise<ApiResponse<CreditForm>> {
  return createResource({ url: `${CREDIT_REQUESTS}.get_credit_form` }).fetch(params);
}

export function submitCreditRequest(payload: CreditRequestPayload & { sales_invoice: string }) {
  return post<CreditRequest>("submit_credit_request", payload);
}

export function resubmitCreditRequest(payload: CreditRequestPayload & { name: string }) {
  return post<CreditRequest>("resubmit_credit_request", payload);
}

export function withdrawCreditRequest(customer: string, name: string) {
  return post<CreditRequest>("withdraw_credit_request", { customer, name });
}
