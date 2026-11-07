import { computed, ref, watch } from "vue";
import type { Ref } from "vue";
import { debounce } from "frappe-ui";
import type { Branch } from "@/stores/portal";

const SEARCH_DELAY = 250;
const MAX_SHOWN = 50;

export function useBranchSearch(branches: Ref<Branch[]>, selected: Ref<string[]>) {
  const query = ref("");
  const term = ref("");
  const applyQuery = debounce((value: string) => {
    term.value = value.trim().toLowerCase();
  }, SEARCH_DELAY);
  watch(query, (value) => applyQuery(value));

  const titles = computed(() => new Map(branches.value.map((branch) => [branch.name, branch.title])));

  const found = computed(() =>
    branches.value.filter(
      (branch) =>
        !term.value ||
        branch.title.toLowerCase().includes(term.value) ||
        branch.name.toLowerCase().includes(term.value),
    ),
  );

  const options = computed(() => {
    const chosen = new Set(selected.value);
    const picked = found.value.filter((branch) => chosen.has(branch.name));
    const others = found.value.filter((branch) => !chosen.has(branch.name)).slice(0, MAX_SHOWN);
    return [...picked, ...others].map((branch) => ({ label: branch.title, value: branch.name }));
  });

  const hiddenCount = computed(() => Math.max(found.value.length - options.value.length, 0));

  function titleOf(name: string) {
    return titles.value.get(name) ?? name;
  }

  return { query, options, hiddenCount, titleOf };
}
