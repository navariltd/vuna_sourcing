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
  billingAddressHint: string;
  asksForDelivery: boolean;
  deliveryAddressHint: string;
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

    billingAddressHint: "The address your invoices to us come from.",

    asksForDelivery: false,

    deliveryAddressHint: "",
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

    billingAddressHint: "The address we put on your invoices.",

    asksForDelivery: true,

    deliveryAddressHint:
      "Where we should deliver your orders, such as your shop, branch or warehouse.",
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
