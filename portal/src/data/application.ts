import { createResource } from "frappe-ui";
import type { PartyType } from "@/data/parties";

export interface RequiredDocument {
  document_type: string;
  is_mandatory: number;
  description: string | null;
  has_expiry?: number;
  attachment?: string | null;
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
  require_bank_details: number;
  require_shipping_address: number;
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
  bank: string | null;
  bank_account_no: string | null;
  account_holder_name: string | null;
  iban: string | null;
  branch_code: string | null;
  swift_number: string | null;
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

export function attachmentUploadUrl(documentType?: string | null) {
  const url = "/api/method/vuna_sourcing.api.onboarding.upload_attachment";
  return documentType ? `${url}?document_type=${encodeURIComponent(documentType)}` : url;
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
