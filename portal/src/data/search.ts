import { createResource } from "frappe-ui";
import { LOOKS } from "@/data/accents";
import type { DocumentLook } from "@/data/accents";
import type { PartyType } from "@/data/parties";
import type { ApiResponse } from "@/types/api";

export type SearchDoctype =
  | "Quotation"
  | "Sales Order"
  | "Delivery Note"
  | "Sales Invoice"
  | "Credit Note Request"
  | "Request for Quotation"
  | "Supplier Quotation"
  | "Purchase Order"
  | "Purchase Invoice";

export interface SearchResult {
  name: string;
  date: string | null;
  detail: string | null;
  status: string | null;
  amount: number | null;
  currency: string | null;
}

export interface SearchGroup {
  doctype: SearchDoctype;
  results: SearchResult[];
}

export interface SearchPage {
  query: string;
  groups: SearchGroup[];
}

export const MIN_SEARCH = 2;

export const SEARCH_GROUPS: Record<
  SearchDoctype,
  { label: string; route: string; look: DocumentLook; detail?: string }
> = {
  Quotation: { label: "Quotations", route: "QuotationDetail", look: LOOKS.quotation },
  "Sales Order": {
    label: "Orders",
    route: "SalesOrderDetail",
    look: LOOKS.salesOrder,
    detail: "Your PO",
  },
  "Delivery Note": {
    label: "Deliveries",
    route: "DeliveryNoteDetail",
    look: LOOKS.deliveryNote,
    detail: "Your PO",
  },
  "Sales Invoice": {
    label: "Invoices",
    route: "SalesInvoiceDetail",
    look: LOOKS.salesInvoice,
    detail: "Your PO",
  },
  "Credit Note Request": {
    label: "Credit note requests",
    route: "CreditRequestDetail",
    look: LOOKS.creditRequest,
    detail: "Invoice",
  },
  "Request for Quotation": { label: "Requests for quotation", route: "RfqDetail", look: LOOKS.rfq },
  "Supplier Quotation": {
    label: "Your quotations",
    route: "SupplierQuotationDetail",
    look: LOOKS.supplierQuotation,
  },
  "Purchase Order": {
    label: "Purchase orders",
    route: "PurchaseOrderDetail",
    look: LOOKS.purchaseOrder,
  },
  "Purchase Invoice": {
    label: "Invoices",
    route: "PurchaseInvoiceDetail",
    look: LOOKS.purchaseInvoice,
    detail: "Your invoice",
  },
};

export function searchDocuments(
  partyType: PartyType,
  party: string,
  query: string,
): Promise<ApiResponse<SearchPage>> {
  return createResource({
    url: "vuna_sourcing.api.transactions.search.search_documents",
  }).fetch({ party_type: partyType, party, query });
}
