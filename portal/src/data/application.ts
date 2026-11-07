import { createResource } from "frappe-ui";
import type { PartyType } from "@/data/parties";
import { isOk } from "@/types/api";
import type { ApiResponse } from "@/types/api";

export interface RequiredDocument {
  document_type: string;
  is_mandatory: number;
  description: string | null;
  has_expiry?: boolean | number;
  allowed_file_types?: string[];
  max_file_size_mb?: number | null;
  attachment?: string | null;
  file_name?: string | null;
  file_size?: number | null;
  document_number?: string | null;
  issue_date?: string | null;
  expiry_date?: string | null;
  idx?: number;
}

export interface ApplicationContact {
  first_name: string | null;
  last_name: string | null;
  designation: string | null;
  email_id: string | null;
  mobile_no: string | null;
  is_primary_contact: number;
  is_billing_contact: number;
}

export interface ApplicationAddress {
  address_type: string;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  pincode: string | null;
  country: string | null;
  is_primary_address: number;
  is_shipping_address: number;
}

export interface OnboardingType {
  name: string;
  party_type: PartyType;
  entity_type: string;
  description: string | null;
  is_default: number;
  require_tax_id: number;
  require_registration_number: number;
  documents: RequiredDocument[];
}

export interface Application {
  name: string;
  docstatus: number;
  onboarding_status: string | null;
  review_remarks: string | null;
  party: string | null;
  party_type: PartyType | null;
  entity_type: string | null;
  onboarding_template: string | null;
  party_name: string | null;
  company_logo: string | null;
  country: string | null;
  tax_id: string | null;
  registration_number: string | null;
  website: string | null;
  contacts: ApplicationContact[];
  addresses: ApplicationAddress[];
  documents: RequiredDocument[];
  can_edit: boolean;
  is_correction: boolean;
}

export interface ApplicationProgress {
  missing_details: string[];
  missing_documents: string[];
  documents_attached: number;
  documents_required: number;
  can_submit: boolean;
}

export function blankContact(patch: Partial<ApplicationContact> = {}): ApplicationContact {
  return {
    first_name: null,
    last_name: null,
    designation: null,
    email_id: null,
    mobile_no: null,
    is_primary_contact: 0,
    is_billing_contact: 0,
    ...patch,
  };
}

export function blankAddress(patch: Partial<ApplicationAddress> = {}): ApplicationAddress {
  return {
    address_type: "Billing",
    address_line1: null,
    address_line2: null,
    city: null,
    state: null,
    pincode: null,
    country: null,
    is_primary_address: 0,
    is_shipping_address: 0,
    ...patch,
  };
}

export function fullName(contact: Pick<ApplicationContact, "first_name" | "last_name"> | null | undefined) {
  return [contact?.first_name, contact?.last_name].filter(Boolean).join(" ");
}

export function oneLineAddress(address: ApplicationAddress | null | undefined) {
  if (!address) return "";
  return [address.address_line1, address.city, address.country].filter(Boolean).join(", ");
}

export const onboardingTypes = createResource({
  url: "vuna_sourcing.api.onboarding.get_onboarding_types",
  auto: false,
  cache: "vuna-sourcing:onboarding-types",
});

export function createApplicationResource() {
  return createResource({
    url: "vuna_sourcing.api.onboarding.get_application",
    auto: false,
  });
}

export function saveApplication(values: Partial<Application>, name?: string | null) {
  return createResource({
    url: "vuna_sourcing.api.onboarding.save_application",
    method: "POST",
  }).submit({ values, name: name || null });
}

export function submitApplication(name: string) {
  return createResource({
    url: "vuna_sourcing.api.onboarding.submit_application",
    method: "POST",
  }).submit({ name });
}

export function uploadEndpoint(
  application: string,
  options: { documentType?: string | null; purpose?: "logo" } = {},
) {
  const query = new URLSearchParams({
    method: "vuna_sourcing.api.onboarding.attach_uploaded_file",
    application,
  });
  if (options.documentType) query.set("document_type", options.documentType);
  if (options.purpose) query.set("purpose", options.purpose);
  return `/api/method/upload_file?${query}`;
}

export interface UploadedAttachment {
  file_url: string;
  file_name: string;
  file_size: number | null;
}

export function uploadedAttachment(response: unknown): UploadedAttachment {
  const envelope = response as ApiResponse<UploadedAttachment>;
  if (!isOk(envelope)) throw new Error(envelope?.message || "The upload did not go through.");
  return envelope.data;
}

export function fileExtension(name: string | null | undefined) {
  const clean = (name ?? "").split("?")[0] ?? "";
  return clean.includes(".") ? clean.split(".").pop()!.toLowerCase() : "";
}

export function fileSize(bytes: number | null | undefined) {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function uploadProblem(file: File, document: RequiredDocument): string | null {
  const allowed = (document.allowed_file_types ?? []).map((type) =>
    type.toLowerCase().replace(/^\./, ""),
  );
  const extension = fileExtension(file.name);
  if (allowed.length && !allowed.includes(extension)) {
    return `${extension ? extension.toUpperCase() : "This"} files are not accepted for ${
      document.document_type
    }. Use ${allowed.map((type) => type.toUpperCase()).join(", ")}.`;
  }
  const limit = Number(document.max_file_size_mb || 0);
  if (limit && file.size > limit * 1024 * 1024) {
    return `This file is ${fileSize(file.size)}. The limit is ${limit} MB.`;
  }
  return null;
}

export function documentProblems(document: RequiredDocument, today: string): string[] {
  const problems: string[] = [];
  if (!document.attachment) {
    if (document.is_mandatory) problems.push("Attach this document");
    return problems;
  }
  if (document.has_expiry) {
    if (!document.expiry_date) problems.push("Add the expiry date");
    else if (document.expiry_date < today)
      problems.push("This document has expired. Attach a current one");
  }
  if (document.issue_date && document.issue_date > today)
    problems.push("The issue date cannot be in the future");
  if (
    document.issue_date &&
    document.expiry_date &&
    document.expiry_date < document.issue_date
  )
    problems.push("The expiry date cannot be before the issue date");
  return problems;
}

export function localToday() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export function fetchProgress(name: string) {
  return createResource({
    url: "vuna_sourcing.api.onboarding.get_application_progress",
  }).fetch({ name });
}

export function resubmitApplication(name: string, values: Partial<Application>) {
  return createResource({
    url: "vuna_sourcing.api.onboarding.resubmit_application",
    method: "POST",
  }).submit({ name, values });
}

export const myApplications = createResource({
  url: "vuna_sourcing.api.onboarding.get_my_applications",
  auto: false,
});

export type BadgeTheme = "gray" | "red" | "blue" | "green" | "amber" | "violet";

export const STATUS_THEME: Record<string, BadgeTheme> = {
  "Pending Review": "blue",
  Approved: "green",
  Rejected: "red",
  "Returned for Correction": "amber",
};

export async function downloadApplication(name: string) {
  const response = (await createResource({
    url: "vuna_sourcing.api.onboarding.download_application",
  }).fetch({ name })) as ApiResponse<{ filename: string; content: string }>;

  if (!isOk(response)) throw new Error(response.message || "We could not prepare the download.");

  const bytes = Uint8Array.from(atob(response.data.content), (char) => char.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = response.data.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export interface TaxIdFormat {
  label: string;
  pattern: string;
  example: string;
  hint: string;
}

export const taxIdFormats = createResource({
  url: "vuna_sourcing.api.onboarding.get_tax_id_formats",
  cache: "vuna-sourcing:tax-id-formats",
  auto: false,
});

export function normaliseTaxId(value: string | null | undefined, format: TaxIdFormat | null) {
  if (!value) return value ?? null;
  return format ? value.replace(/\s+/g, "").toUpperCase() : value.trim();
}

export function taxIdProblem(value: string | null | undefined, format: TaxIdFormat | null) {
  const tax = normaliseTaxId(value, format);
  if (!format || !tax) return null;
  return new RegExp(format.pattern).test(tax)
    ? null
    : `Check your ${format.label}. It should be ${format.hint.charAt(0).toLowerCase()}${format.hint.slice(1)} For example ${format.example}.`;
}
