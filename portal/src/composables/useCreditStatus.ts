import { computed, ref, watch } from "vue";
import { errorText } from "@/data/orders";
import { fetchCreditStatus } from "@/data/credit";
import type { CompanyCredit, CreditStatus } from "@/data/credit";
import { usePortalStore } from "@/stores/portal";
import { isOk } from "@/types/api";

const status = ref<CreditStatus | null>(null);
const loadedFor = ref<string | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
let request = 0;

export function useCreditStatus() {
  const portal = usePortalStore();

  const customer = computed(() =>
    portal.features.credit_limits &&
    portal.activeParty?.party_type === "Customer" &&
    portal.activeParty.all_branches !== false
      ? portal.activeParty.name
      : null,
  );

  async function load(force = false) {
    const target = customer.value;
    if (!target) {
      status.value = null;
      loadedFor.value = null;
      return;
    }
    if (!force && loadedFor.value === target && status.value) return;

    const current = ++request;
    loading.value = true;
    error.value = null;
    try {
      const response = await fetchCreditStatus(target);
      if (current !== request) return;
      if (isOk(response)) {
        status.value = response.data;
        loadedFor.value = target;
      } else {
        status.value = null;
        error.value = response.message;
      }
    } catch (failure) {
      if (current !== request) return;
      status.value = null;
      error.value = errorText(failure, "We could not load your credit details.");
    } finally {
      if (current === request) loading.value = false;
    }
  }

  watch(customer, () => load(), { immediate: true });

  const rows = computed(() => (customer.value ? status.value?.rows ?? [] : []));
  const overRows = computed(() => rows.value.filter((row) => row.state === "over"));
  const nearRows = computed(() => rows.value.filter((row) => row.state === "near"));

  function forCompany(company: string | null | undefined): CompanyCredit | null {
    return rows.value.find((row) => row.company === company) ?? null;
  }

  return {
    enabled: computed(() => !!customer.value),
    rows,
    overRows,
    nearRows,
    loading,
    error,
    reload: () => load(true),
    forCompany,
  };
}
