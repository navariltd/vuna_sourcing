export type PartyType = "Supplier" | "Customer";

export const PARTY_TYPES: PartyType[] = ["Supplier", "Customer"];

export interface PartyCopy {
  noun: string;
  icon: string;
  headline: string;
  pitch: string;
  outcome: string;
  primaryContactHint: string;
  billingContactHint: string;
  registeredAddressHint: string;
  asksForDelivery: boolean;
  extraAddressLabel: string;
  extraAddressHint: string;
  extraAddressType: string;
  bankHint: string;
}

export const PARTY_COPY: Record<PartyType, PartyCopy> = {
  Supplier: {
    noun: "supplier",
    icon: "lucide-truck",

    headline: "Sell to us",

    pitch:
      "Provide goods or services to us, manage your company details, and keep track of orders and payments in one place.",

    outcome:
      "Receive purchase orders, manage your documents, and track payments from your account.",

    primaryContactHint:
      "The person we should contact about orders, deliveries, and day-to-day communication.",

    billingContactHint:
      "The person in your accounts team who should receive purchase orders, statements, and payment information.",

    registeredAddressHint: "Your company's official registered address.",

    asksForDelivery: false,

    extraAddressLabel: "Add a dispatch or warehouse address",

    extraAddressHint:
      "Add a location where we collect goods from or where you dispatch orders.",

    extraAddressType: "Warehouse",

    bankHint: "The bank account where we should send your payments.",
  },

  Customer: {
    noun: "customer",
    icon: "lucide-shopping-bag",

    headline: "Buy from us",

    pitch:
      "Purchase goods or services from us, manage your company details, and keep track of orders, invoices, and deliveries.",

    outcome:
      "Place orders, view invoices, and track deliveries from your account.",

    primaryContactHint:
      "The person we should contact about orders, deliveries, and day-to-day communication.",

    billingContactHint:
      "The person in your accounts team who should receive invoices, statements, and payment information.",

    registeredAddressHint: "Your company's official registered address.",

    asksForDelivery: true,

    extraAddressLabel: "Add a delivery address",

    extraAddressHint:
      "Add a site, branch, office, or warehouse where we should deliver your orders.",

    extraAddressType: "Shipping",

    bankHint:
      "Used when we need to process a refund or another payment to your business.",
  },
};

export function partyCopy(
  partyType: string | null | undefined,
): PartyCopy | null {
  return partyType && partyType in PARTY_COPY
    ? PARTY_COPY[partyType as PartyType]
    : null;
}

export function joinNouns(partyTypes: string[], conjunction = "or") {
  const nouns = partyTypes.map((p) => partyCopy(p)?.noun ?? p.toLowerCase());
  if (nouns.length <= 1) return nouns[0] ?? "";
  return `${nouns.slice(0, -1).join(", ")} ${conjunction} ${nouns[nouns.length - 1]}`;
}
