import { createResource } from "frappe-ui";
import type { ApiResponse } from "@/types/api";

export interface OrderAddress {
  name: string;
  title: string;
  address_type: string | null;
  lines: string;
}

export interface OrderLineView {
  item_code: string;
  item_name: string;
  image: string | null;
  qty: number;
  uom: string;
  uoms: OrderableUom[];
  rate: number;
  amount: number;
}

export interface OrderView {
  name: string | null;
  company: string;
  currency: string;
  delivery_date: string | null;
  po_no: string | null;
  shipping_address: string | null;
  status: "Pending" | "Submitted" | null;
  items: OrderLineView[];
  net_total: number;
  total_taxes: number | null;
  grand_total: number;
}

export interface OrderForm {
  companies: string[];
  addresses: OrderAddress[];
  today: string;
  order: OrderView | null;
}

export interface OrderableUom {
  uom: string;
  conversion_factor: number;
}

export interface OrderableItem {
  item_code: string;
  item_name: string;
  description: string | null;
  image: string | null;
  item_group: string | null;
  stock_uom: string;
  uoms: OrderableUom[];
  uom: string;
  rate: number | null;
}

export interface OrderableItemsPage {
  currency: string | null;
  has_more: boolean;
  rows: OrderableItem[];
}

export interface OrderLineInput {
  item_code: string;
  uom: string;
  qty: number;
}

export interface OrderPayload {
  customer: string;
  company: string | null;
  items: OrderLineInput[];
  name?: string | null;
  delivery_date?: string | null;
  shipping_address?: string | null;
  po_no?: string | null;
}

const ORDERS = "vuna_sourcing.api.transactions.customer_orders";

function post<T>(method: string, payload: object): Promise<ApiResponse<T>> {
  return createResource({ url: `${ORDERS}.${method}`, method: "POST" }).submit(
    payload,
  );
}

export function fetchOrderForm(
  customer: string,
  name?: string | null,
): Promise<ApiResponse<OrderForm>> {
  return createResource({ url: `${ORDERS}.get_order_form` }).fetch({
    customer,
    name: name || null,
  });
}

export interface OrderCategory {
  name: string;
  count: number;
}

export interface OrderCategoryPage {
  rows: OrderCategory[];
  has_more: boolean;
  all_items: number | null;
}

export function fetchOrderCategories(params: {
  customer: string;
  company: string | null;
  search?: string | null;
  start?: number;
  limit?: number;
}): Promise<ApiResponse<OrderCategoryPage>> {
  return createResource({ url: `${ORDERS}.get_order_categories` }).fetch(params);
}

export function fetchOrderableItems(params: {
  customer: string;
  company: string | null;
  search?: string | null;
  item_group?: string | null;
  start?: number;
  limit?: number;
}): Promise<ApiResponse<OrderableItemsPage>> {
  return createResource({ url: `${ORDERS}.get_orderable_items` }).fetch(params);
}

export function priceOrder(payload: Omit<OrderPayload, "name" | "po_no">) {
  return post<OrderView>("price_order", payload);
}

export function saveOrder(payload: OrderPayload) {
  return post<OrderView>("save_order", payload);
}

export function submitOrder(payload: OrderPayload) {
  return post<OrderView>("submit_order", payload);
}

export function clearOrder(customer: string, name: string) {
  return post<OrderView>("clear_order", { customer, name });
}

export function deleteOrder(customer: string, name: string) {
  return post<null>("delete_order", { customer, name });
}

export function withdrawOrder(customer: string, name: string) {
  return post<{ name: string }>("withdraw_order", { customer, name });
}

export function errorText(error: any, fallback: string) {
  return error?.messages?.[0] || error?.message || fallback;
}
