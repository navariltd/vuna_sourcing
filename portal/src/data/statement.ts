import { createResource } from "frappe-ui";

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
  companies: StatementSection[];
}

export const customerStatement = createResource({
  url: "vuna_sourcing.api.transactions.customer.get_account_statement",
  auto: false,
});

export const supplierStatement = createResource({
  url: "vuna_sourcing.api.transactions.supplier.get_account_statement",
  auto: false,
});

