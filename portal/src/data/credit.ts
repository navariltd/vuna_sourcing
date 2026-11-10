import { createResource } from "frappe-ui";
import type { BadgeTheme } from "@/data/application";
import type { ApiResponse } from "@/types/api";

export type CreditState = "over" | "near" | "within";

export interface CompanyCredit {
  company: string;
  currency: string;
  credit_limit: number;
  used: number;
  unpaid_invoices: number;
  not_yet_invoiced: number;
  available: number;
  over_by: number;
  used_percent: number;
  state: CreditState;
}

export interface CreditStatus {
  rows: CompanyCredit[];
  over_limit: string[];
  near_limit: string[];
}

export const CREDIT_STATE_THEME: Record<CreditState, BadgeTheme> = {
  over: "red",
  near: "amber",
  within: "green",
};

export const CREDIT_STATE_LABEL: Record<CreditState, string> = {
  over: "Over limit",
  near: "Close to limit",
  within: "Within limit",
};

const CREDIT = "vuna_sourcing.api.transactions.credit_limits";

export function fetchCreditStatus(customer: string): Promise<ApiResponse<CreditStatus>> {
  return createResource({ url: `${CREDIT}.get_credit_status` }).fetch({ customer });
}

export function orderCreditImpact(
  row: CompanyCredit | null | undefined,
  orderTotal: number | null | undefined,
) {
  if (!row) return null;
  const after = row.used + Math.max(orderTotal ?? 0, 0);
  return {
    alreadyOver: row.state === "over",
    overAfter: Math.max(after - row.credit_limit, 0),
  };
}
