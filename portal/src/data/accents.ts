export type Accent = "purple" | "cyan" | "blue" | "green" | "amber" | "pink" | "gray";

export interface AccentClasses {
  tile: string;
  icon: string;
  panel: string;
}

export const ACCENTS: Record<Accent, AccentClasses> = {
  purple: {
    tile: "bg-surface-purple-2 text-ink-purple-7",
    icon: "text-ink-purple-6",
    panel: "bg-surface-purple-1 border-outline-purple-2",
  },
  cyan: {
    tile: "bg-surface-cyan-2 text-ink-cyan-7",
    icon: "text-ink-cyan-6",
    panel: "bg-surface-cyan-1 border-outline-cyan-2",
  },
  blue: {
    tile: "bg-surface-blue-2 text-ink-blue-7",
    icon: "text-ink-blue-6",
    panel: "bg-surface-blue-1 border-outline-blue-2",
  },
  green: {
    tile: "bg-surface-green-2 text-ink-green-7",
    icon: "text-ink-green-6",
    panel: "bg-surface-green-1 border-outline-green-2",
  },
  amber: {
    tile: "bg-surface-amber-2 text-ink-amber-7",
    icon: "text-ink-amber-6",
    panel: "bg-surface-amber-1 border-outline-amber-2",
  },
  pink: {
    tile: "bg-surface-pink-2 text-ink-pink-7",
    icon: "text-ink-pink-6",
    panel: "bg-surface-pink-1 border-outline-pink-2",
  },
  gray: {
    tile: "bg-surface-gray-2 text-ink-gray-7",
    icon: "text-ink-gray-6",
    panel: "border-outline-gray-2",
  },
};

export interface DocumentLook {
  icon: string;
  accent: Accent;
}

export const LOOKS = {
  rfq: { icon: "lucide-file-text", accent: "purple" },
  supplierQuotation: { icon: "lucide-file-check", accent: "cyan" },
  purchaseOrder: { icon: "lucide-package", accent: "blue" },
  purchaseInvoice: { icon: "lucide-receipt", accent: "amber" },
  debitNote: { icon: "lucide-receipt-cent", accent: "pink" },
  quotation: { icon: "lucide-file-badge", accent: "cyan" },
  salesOrder: { icon: "lucide-shopping-cart", accent: "blue" },
  deliveryNote: { icon: "lucide-truck", accent: "green" },
  salesInvoice: { icon: "lucide-receipt-text", accent: "amber" },
  creditNote: { icon: "lucide-receipt-cent", accent: "pink" },
  receivable: { icon: "lucide-wallet", accent: "amber" },
  payable: { icon: "lucide-wallet", accent: "amber" },
  application: { icon: "lucide-folder-clock", accent: "gray" },
  onboard: { icon: "lucide-file-pen-line", accent: "gray" },
} satisfies Record<string, DocumentLook>;

export const PARTY_ACCENTS: Record<"Supplier" | "Customer", Accent> = {
  Supplier: "purple",
  Customer: "cyan",
};
