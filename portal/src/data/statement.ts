import { createResource } from "frappe-ui";
import type { ApiResponse } from "@/types/api";

export interface StatementRow {
  voucher_type: string;
  voucher_no: string;
  posting_date: string;
  due_date: string | null;
  bill_no: string | null;
  po_no: string | null;
  invoiced: number;
  paid: number;
  credit_note: number;
  outstanding: number;
  age: number;
  currency: string | null;
}

export interface StatementSection {
  company: string;
  currency: string | null;
  rows: StatementRow[];
  totals: { invoiced: number; paid: number; credit_note: number; outstanding: number };
}

export interface Statement {
  report_date: string | null;
  companies: string[];
  company: string | null;
  section: StatementSection | null;
  branch_limited: boolean;
}

export function fetchStatement(
  side: "Customer" | "Supplier",
  party: string,
  company: string | null,
): Promise<ApiResponse<Statement>> {
  const module = side === "Customer" ? "customer" : "supplier";
  return createResource({
    url: `vuna_sourcing.api.transactions.${module}.get_account_statement`,
  }).fetch(side === "Customer" ? { customer: party, company } : { supplier: party, company });
}
