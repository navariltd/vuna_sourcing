import { onBeforeUnmount, readonly, ref } from "vue";

const MOBILE = "(max-width: 767px)";
const WIDE = "(min-width: 1280px)";
const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

function useMediaQuery(media: string) {
  const matches = ref(false);

  const query = window.matchMedia?.(media);
  if (query) {
    matches.value = query.matches;
    const onChange = (event: MediaQueryListEvent) => (matches.value = event.matches);
    query.addEventListener("change", onChange);
    onBeforeUnmount(() => query.removeEventListener("change", onChange));
  }

  return readonly(matches);
}

export function useIsMobile() {
  return useMediaQuery(MOBILE);
}

export function useIsWide() {
  return useMediaQuery(WIDE);
}

export function usePrefersReducedMotion() {
  return useMediaQuery(REDUCED_MOTION);
}
