import { onBeforeUnmount, ref, watch } from "vue";
import type { Ref } from "vue";
import { errorText, fetchOrderCategories } from "@/data/orders";
import type { OrderCategory } from "@/data/orders";
import { isOk } from "@/types/api";

const PAGE_SIZE = 24;
const SEARCH_DELAY = 250;

export function useOrderCategories(
  customer: Ref<string | null>,
  company: Ref<string | null>,
  active: Ref<boolean>,
) {
  const rows = ref<OrderCategory[]>([]);
  const hasMore = ref(false);
  const allItems = ref<number | null>(null);
  const query = ref("");
  const loading = ref(false);
  const error = ref<string | null>(null);
  let request = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  async function load(append = false) {
    const current = ++request;
    if (!customer.value || !company.value || !active.value) {
      rows.value = [];
      hasMore.value = false;
      allItems.value = null;
      loading.value = false;
      return;
    }

    loading.value = true;
    error.value = null;
    try {
      const response = await fetchOrderCategories({
        customer: customer.value,
        company: company.value,
        search: query.value.trim() || null,
        start: append ? rows.value.length : 0,
        limit: PAGE_SIZE,
      });
      if (current !== request) return;
      if (!isOk(response)) {
        error.value = response.message || "We could not load the categories.";
        return;
      }
      rows.value = append ? [...rows.value, ...response.data.rows] : response.data.rows;
      hasMore.value = response.data.has_more;
      if (response.data.all_items != null) allItems.value = response.data.all_items;
    } catch (failure) {
      if (current === request) error.value = errorText(failure, "We could not load the categories.");
    } finally {
      if (current === request) loading.value = false;
    }
  }

  watch([customer, company, active], () => {
    query.value = "";
    allItems.value = null;
    load();
  });

  watch(query, () => {
    clearTimeout(timer);
    timer = setTimeout(() => load(), SEARCH_DELAY);
  });

  onBeforeUnmount(() => clearTimeout(timer));

  return {
    rows,
    hasMore,
    allItems,
    query,
    loading,
    error,
    reload: () => load(),
    loadMore: () => load(true),
  };
}

export type OrderCategories = ReturnType<typeof useOrderCategories>;
