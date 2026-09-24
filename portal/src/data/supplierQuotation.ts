import { createResource } from "frappe-ui";
import type { BadgeTheme } from "@/data/application";

export type SupplierQuotationStatus =
  | "Draft"
  | "Submitted"
  | "Stopped"
  | "Cancelled"
  | "Expired";

export interface SupplierQuotationRow {
  name: string;
  supplier: string;
  transaction_date: string;
  valid_till: string | null;
  quotation_number: string | null;
  total: number | null;
  currency: string | null;
  items: number;
  rfq: string | null;
  status: SupplierQuotationStatus;
}

export interface SupplierQuotationPage {
  rows: SupplierQuotationRow[];
  total: number;
  start: number;
  limit: number;
  counts: Record<string, number>;
}

export const SUPPLIER_QUOTATION_STATUS_THEME: Record<
  SupplierQuotationStatus,
  BadgeTheme
> = {
  Draft: "blue",
  Submitted: "green",
  Stopped: "amber",
  Cancelled: "red",
  Expired: "gray",
};

export interface SupplierQuotationItem {
  name: string;
  item_code: string;
  item_name: string | null;
  description: string | null;
  qty: number;
  uom: string | null;
  rate: number | null;
  amount: number | null;
  lead_time_days: number | null;
  rfq: string | null;
}

export interface SupplierQuotation {
  name: string;
  supplier: string;
  status: SupplierQuotationStatus;
  transaction_date: string;
  valid_till: string | null;
  quotation_number: string | null;
  currency: string | null;
  total: number | null;
  grand_total: number | null;
  terms: string | null;
  rfq: string | null;
  items: SupplierQuotationItem[];
}

export const supplierQuotationList = createResource({
  url: "vuna_sourcing.api.supplier_quotation.get_supplier_quotations",
  auto: false,
});

export function createSupplierQuotationResource() {
  return createResource({
    url: "vuna_sourcing.api.supplier_quotation.get_supplier_quotation",
    auto: false,
  });
}
