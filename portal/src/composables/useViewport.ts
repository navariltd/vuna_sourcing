import { onBeforeUnmount, readonly, ref } from "vue";

const MOBILE = "(max-width: 767px)";

export function useIsMobile() {
  const isMobile = ref(false);

  const query = window.matchMedia?.(MOBILE);
  if (query) {
    isMobile.value = query.matches;
    const onChange = (event: MediaQueryListEvent) => (isMobile.value = event.matches);
    query.addEventListener("change", onChange);
    onBeforeUnmount(() => query.removeEventListener("change", onChange));
  }

  return readonly(isMobile);
}
