import { createResource } from "frappe-ui";
import type { BadgeTheme } from "@/data/application";

export type RfqStatus = "Invited" | "Submitted" | "Declined" | "Closed";

export interface RfqQuote {
  name: string;
  docstatus: number;
  status: string | null;
  valid_till: string | null;
  quotation_number: string | null;
  total: number | null;
  currency: string | null;
}

export interface RfqItem {
  name: string;
  item_code: string;
  item_name: string | null;
  description: string | null;
  qty: number;
  uom: string | null;
  required_by: string | null;
  supplier_part_no: string | null;
  rate: number | null;
  lead_time_days: number | null;
}

export interface RfqAttachment {
  file_name: string;
  file_url: string;
}

export interface RfqRow {
  name: string;
  supplier: string;
  transaction_date: string;
  required_by: string | null;
  company: string;
  items: number;
  status: RfqStatus;
  quote: RfqQuote | null;
}

export interface Rfq {
  name: string;
  supplier: string;
  company: string;
  transaction_date: string;
  required_by: string | null;
  closed: boolean;
  status: RfqStatus;
  can_quote: boolean;
  terms: string | null;
  items: RfqItem[];
  quote: RfqQuote | null;
  attachments: RfqAttachment[];
}

export interface QuoteLine {
  rfq_item: string;
  rate: number | null;
  lead_time_days: number | null;
}

export const RFQ_STATUS_THEME: Record<RfqStatus, BadgeTheme> = {
  Invited: "blue",
  Submitted: "green",
  Declined: "gray",
  Closed: "gray",
};

export const RFQ_STATUS_HINT: Record<RfqStatus, string> = {
  Invited: "Waiting for your prices",
  Submitted: "With the buyer",
  Declined: "You are not quoting",
  Closed: "Past the date quotes were needed",
};

export interface RfqPage {
  rows: RfqRow[];
  total: number;
  start: number;
  limit: number;
  counts: Record<string, number>;
}

export const RFQ_STATUSES: RfqStatus[] = ["Invited", "Submitted", "Declined", "Closed"];

export const rfqList = createResource({
  url: "vuna_sourcing.api.transactions.supplier.get_rfqs",
  auto: false,
});

export function createRfqResource() {
  return createResource({
    url: "vuna_sourcing.api.transactions.supplier.get_rfq",
    auto: false,
  });
}

export function sendQuote(payload: {
  name: string;
  supplier: string;
  items: QuoteLine[];
  quotation_number?: string | null;
  valid_till?: string | null;
}) {
  return createResource({
    url: "vuna_sourcing.api.transactions.supplier.send_quote",
    method: "POST",
  }).submit(payload);
}

export function declineQuote(name: string, supplier: string, reason: string) {
  return createResource({
    url: "vuna_sourcing.api.transactions.supplier.decline_quote",
    method: "POST",
  }).submit({ name, supplier, reason });
}
