import { computed, inject, onBeforeUnmount, provide, ref, watch } from "vue";
import type { InjectionKey, Ref } from "vue";
import { toast } from "frappe-ui";
import {
  clearOrder,
  deleteOrder,
  errorText,
  fetchOrderForm,
  priceOrder,
  saveOrder,
  submitOrder,
} from "@/data/orders";
import type {
  OrderForm,
  OrderLineView,
  OrderPayload,
  OrderView,
  OrderableItem,
  OrderableUom,
  PoDocument,
} from "@/data/orders";
import { isOk } from "@/types/api";
import type { ApiResponse } from "@/types/api";

export interface CartLine {
  item_code: string;
  item_name: string;
  image: string | null;
  uom: string;
  uoms: OrderableUom[];
  qty: number;
}

function cartLinesFrom(items: OrderLineView[]): CartLine[] {
  return items.map(({ item_code, item_name, image, uom, uoms, qty }) => ({
    item_code,
    item_name,
    image,
    uom,
    uoms,
    qty,
  }));
}

export function useOrderDraft(customer: Ref<string | null>, name: Ref<string | undefined>) {
  const form = ref<OrderForm | null>(null);
  const loading = ref(false);
  const unavailable = ref<string | null>(null);
  const loadedFor = ref<string | null>(null);

  const orderName = ref<string | null>(null);
  const company = ref<string | null>(null);
  const address = ref<string | null>(null);
  const deliveryDate = ref<string | null>(null);
  const poNo = ref("");
  const poDocument = ref<PoDocument | null>(null);
  const lines = ref<CartLine[]>([]);
  const savedSnapshot = ref("");

  const priced = ref<OrderView | null>(null);
  const pricing = ref(false);
  const pricingError = ref<string | null>(null);
  const pricedKey = ref("");
  let priceTimer: ReturnType<typeof setTimeout> | undefined;
  let priceRequest = 0;

  const busy = ref<"draft" | "send" | "delete" | "clear" | null>(null);
  const errorMessage = ref<string | null>(null);

  const companies = computed(() => form.value?.companies ?? []);
  const addresses = computed(() => form.value?.addresses ?? []);
  const currency = computed(() => priced.value?.currency ?? null);
  const units = computed(() => lines.value.reduce((total, line) => total + line.qty, 0));

  function orderedItems() {
    return lines.value.map(({ item_code, uom, qty }) => ({ item_code, uom, qty }));
  }

  function snapshot() {
    return JSON.stringify({
      company: company.value,
      address: address.value,
      deliveryDate: deliveryDate.value,
      poNo: poNo.value.trim(),
      poDocument: poDocument.value?.file_url ?? null,
      lines: orderedItems(),
    });
  }

  const dirty = computed(() => snapshot() !== savedSnapshot.value);

  function priceKey() {
    return JSON.stringify({ company: company.value, address: address.value, items: orderedItems() });
  }

  function adopt(order: OrderView | null) {
    orderName.value = order?.name ?? null;
    lines.value = cartLinesFrom(order?.items ?? []);
    priced.value = order;
    pricedKey.value = priceKey();
    pricingError.value = null;
    savedSnapshot.value = snapshot();
  }

  function fill(data: OrderForm) {
    const order = data.order;
    company.value = order?.company ?? (data.companies.length === 1 ? data.companies[0]! : null);
    address.value =
      order?.shipping_address ?? (data.addresses.length === 1 ? data.addresses[0]!.name : null);
    deliveryDate.value = order?.delivery_date ?? null;
    poNo.value = order?.po_no ?? "";
    poDocument.value = order?.po_document ?? null;
    adopt(order);
  }

  async function load() {
    if (!customer.value) return;
    if (
      name.value &&
      name.value === orderName.value &&
      form.value &&
      loadedFor.value === customer.value
    )
      return;

    loading.value = true;
    unavailable.value = null;
    errorMessage.value = null;

    try {
      const response = await fetchOrderForm(customer.value, name.value);
      if (!isOk(response)) {
        form.value = null;
        unavailable.value = response.message || "Ordering is not available for this account.";
        return;
      }
      form.value = response.data;
      loadedFor.value = customer.value;
      fill(response.data);
    } catch (error) {
      form.value = null;
      unavailable.value = errorText(error, "We cannot open this order.");
    } finally {
      loading.value = false;
    }
  }

  watch([customer, name], load, { immediate: true });

  async function runPricing(key: string) {
    const request = ++priceRequest;
    pricing.value = true;

    try {
      const response = await priceOrder({
        customer: customer.value!,
        company: company.value,
        items: orderedItems(),
        delivery_date: deliveryDate.value,
        shipping_address: address.value,
      });
      if (request !== priceRequest) return;

      pricedKey.value = key;
      if (isOk(response)) {
        priced.value = response.data;
        pricingError.value = null;
      } else {
        pricingError.value = response.message;
      }
    } catch (error) {
      if (request !== priceRequest) return;
      pricedKey.value = key;
      pricingError.value = errorText(error, "We could not price your order.");
    } finally {
      if (request === priceRequest) pricing.value = false;
    }
  }

  function schedulePricing() {
    clearTimeout(priceTimer);
    const key = priceKey();
    if (key === pricedKey.value) return;

    if (!customer.value || !company.value || !lines.value.length) {
      priceRequest++;
      pricing.value = false;
      priced.value = null;
      pricedKey.value = key;
      pricingError.value = null;
      return;
    }

    priceTimer = setTimeout(() => runPricing(key), 350);
  }

  watch(priceKey, schedulePricing);

  function refreshPrices() {
    pricedKey.value = "";
    schedulePricing();
  }
  onBeforeUnmount(() => clearTimeout(priceTimer));

  const pricesCurrent = computed(() => priceKey() === pricedKey.value);

  function pricedLine(line: CartLine) {
    if (!pricesCurrent.value) return null;
    return priced.value?.items.find(
      (item) => item.item_code === line.item_code && item.uom === line.uom,
    );
  }

  function lineFor(item_code: string, uom: string) {
    return lines.value.find((line) => line.item_code === item_code && line.uom === uom);
  }

  function remove(line: CartLine) {
    lines.value = lines.value.filter((other) => other !== line);
  }

  function setQty(line: CartLine, value: number) {
    if (!Number.isFinite(value)) return;
    if (value <= 0) remove(line);
    else line.qty = value;
  }

  function add(item: OrderableItem, qty = 1) {
    const existing = lineFor(item.item_code, item.uom);
    if (existing) {
      existing.qty += qty;
      return;
    }
    lines.value.push({
      item_code: item.item_code,
      item_name: item.item_name,
      image: item.image,
      uom: item.uom,
      uoms: item.uoms,
      qty,
    });
  }

  function changeUom(line: CartLine, uom: string) {
    const twin = lineFor(line.item_code, uom);
    if (twin && twin !== line) {
      twin.qty += line.qty;
      remove(line);
      return;
    }
    line.uom = uom;
  }

  watch(poNo, (value) => {
    if (!value.trim()) poDocument.value = null;
  });

  const poRules = computed(() => form.value?.po_document ?? null);
  const needsPoDocument = computed(
    () => !!poRules.value?.required && !!poNo.value.trim() && !poDocument.value,
  );

  const checklist = computed(() => [
    { label: "Add at least one item", done: lines.value.length > 0, toSave: true },
    {
      label: "Choose a delivery address",
      done: addresses.value.length <= 1 || !!address.value,
      toSave: true,
    },
    { label: "Choose the company you are ordering from", done: !!company.value, toSave: true },
    { label: "Attach your LPO document", done: !needsPoDocument.value, toSave: false },
  ]);

  const missing = computed(() => checklist.value.filter((step) => !step.done));
  const ready = computed(() => !missing.value.length && !busy.value);
  const savable = computed(
    () => !missing.value.some((step) => step.toSave) && !busy.value,
  );

  function payload(): OrderPayload {
    return {
      customer: customer.value!,
      company: company.value,
      name: orderName.value,
      items: orderedItems(),
      delivery_date: deliveryDate.value,
      shipping_address: address.value,
      po_no: poNo.value.trim() || null,
      po_document: poNo.value.trim() ? poDocument.value?.file_url ?? null : null,
    };
  }

  async function run<T>(
    kind: "draft" | "send" | "delete" | "clear",
    request: () => Promise<ApiResponse<T>>,
    fallback: string,
  ): Promise<{ data: T; message: string | null } | null> {
    busy.value = kind;
    errorMessage.value = null;

    try {
      const response = await request();
      if (!isOk(response)) {
        errorMessage.value = response.message || fallback;
        return null;
      }
      return { data: response.data, message: response.message };
    } catch (error) {
      errorMessage.value = errorText(error, fallback);
      return null;
    } finally {
      busy.value = null;
    }
  }

  async function saveDraft() {
    if (!savable.value) return null;
    const result = await run(
      "draft",
      () => saveOrder(payload()),
      "We could not save your draft.",
    );
    if (!result) return null;

    adopt(result.data);
    toast.success(result.message || "Draft saved.");
    return result.data;
  }

  async function send() {
    if (!ready.value) return null;
    const result = await run("send", () => submitOrder(payload()), "We could not send your order.");
    if (!result) return null;

    adopt(result.data);
    toast.success(result.message || "Order sent.");
    return result.data;
  }

  async function clearCart() {
    if (!orderName.value) {
      lines.value = [];
      return true;
    }

    const draft = orderName.value;
    const result = await run(
      "clear",
      () => clearOrder(customer.value!, draft),
      "We could not clear your cart.",
    );
    if (!result) return false;

    adopt(result.data);
    toast.success(result.message || "Cart cleared.");
    return true;
  }

  async function removeDraft() {
    if (!orderName.value || !customer.value) return false;
    const draft = orderName.value;
    const result = await run(
      "delete",
      () => deleteOrder(customer.value!, draft),
      "We could not delete this draft.",
    );
    if (!result) return false;

    toast.success(result.message || "Draft deleted.");
    return true;
  }

  return {
    customer,
    form,
    loading,
    unavailable,
    orderName,
    company,
    companies,
    address,
    addresses,
    deliveryDate,
    poNo,
    poDocument,
    poRules,
    needsPoDocument,
    lines,
    units,
    dirty,
    priced,
    pricing,
    pricingError,
    currency,
    busy,
    errorMessage,
    checklist,
    missing,
    ready,
    savable,
    pricedLine,
    refreshPrices,
    lineFor,
    add,
    setQty,
    changeUom,
    remove,
    saveDraft,
    send,
    clearCart,
    removeDraft,
  };
}

export type OrderDraft = ReturnType<typeof useOrderDraft>;

const orderDraftKey: InjectionKey<OrderDraft> = Symbol("orderDraft");

export function provideOrderDraft(draft: OrderDraft) {
  provide(orderDraftKey, draft);
}

export function injectOrderDraft() {
  const draft = inject(orderDraftKey);
  if (!draft) throw new Error("injectOrderDraft needs an order draft provided by the page");
  return draft;
}
