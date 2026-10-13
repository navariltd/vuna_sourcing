import { createResource } from "frappe-ui";
import type { BadgeTheme } from "@/data/application";
import type { ApiResponse } from "@/types/api";

export type RfqStatus = "Invited" | "Draft" | "Bidding" | "Submitted" | "Declined" | "Closed";

export type SupplierSubmissionStatus = "Pending" | "Submitted";

export type BiddingMethod = "Sealed Bid" | "Open Bid";

export interface RfqQuote {
  name: string;
  docstatus: number;
  status: string | null;
  valid_till: string | null;
  quotation_number: string | null;
  total: number | null;
  currency: string | null;
  supplier_submission_status: SupplierSubmissionStatus | null;
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
  closes_at: string | null;
  bidding_method: BiddingMethod | null;
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
  closes_at: string | null;
  bidding_method: BiddingMethod | null;
  sealed: boolean;
  open_bid: boolean;
  closed: boolean;
  status: RfqStatus;
  can_quote: boolean;
  terms: string | null;
  items: RfqItem[];
  quote: RfqQuote | null;
  attachments: RfqAttachment[];
}

export interface OpenBid {
  alias: string;
  rank: number;
  total: number;
  rates: Record<string, number>;
  bid_at: string;
  revisions: number;
  is_you: boolean;
}

export interface YourBid {
  name: string;
  total: number;
  bid_at: string;
  live: boolean;
}

export interface OpenBidBoard {
  currency: string;
  closes_at: string | null;
  closed: boolean;
  bidders: number;
  lowest: number | null;
  lowest_rates: Record<string, number>;
  bids: OpenBid[];
  your_bids: YourBid[];
}

export interface QuoteLine {
  rfq_item: string;
  rate: number | null;
  lead_time_days: number | null;
}

export const RFQ_STATUS_THEME: Record<RfqStatus, BadgeTheme> = {
  Invited: "blue",
  Draft: "amber",
  Bidding: "violet",
  Submitted: "green",
  Declined: "gray",
  Closed: "gray",
};

export const RFQ_STATUS_HINT: Record<RfqStatus, string> = {
  Invited: "Waiting for your prices",
  Draft: "Saved, not sent yet",
  Bidding: "Live open bids you can still improve",
  Submitted: "With the buyer",
  Declined: "You are not quoting",
  Closed: "Bids have closed",
};

export interface RfqPage {
  rows: RfqRow[];
  total: number;
  start: number;
  limit: number;
  counts: Record<string, number>;
}

export const RFQ_STATUSES: RfqStatus[] = [
  "Invited",
  "Draft",
  "Bidding",
  "Submitted",
  "Declined",
  "Closed",
];

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

export function createOpenBidsResource() {
  return createResource({
    url: "vuna_sourcing.api.transactions.open_bid.get_open_bids",
    auto: false,
  });
}

export interface LiveBid {
  name: string;
  supplier: string;
  company: string;
  closes_at: string | null;
  has_bid: boolean;
  status: RfqStatus;
  rank: number | null;
  bidders: number | null;
  lowest: number | null;
  your_total: number | null;
  currency: string | null;
}

export function createLiveBidsResource() {
  return createResource({
    url: "vuna_sourcing.api.transactions.open_bid.get_live_bids",
    auto: false,
  });
}

export function rfqRoute(row: { name: string; status: RfqStatus }) {
  return {
    name: row.status === "Bidding" ? "BidRoom" : "RfqDetail",
    params: { name: row.name },
  };
}

export interface QuotePayload {
  name: string;
  supplier: string;
  items: QuoteLine[];
  quotation_number?: string | null;
  valid_till?: string | null;
}

export function saveQuote(payload: QuotePayload): Promise<ApiResponse<Rfq>> {
  return createResource({
    url: "vuna_sourcing.api.transactions.supplier.save_quote",
    method: "POST",
  }).submit(payload);
}

export function sendQuote(payload: QuotePayload) {
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
