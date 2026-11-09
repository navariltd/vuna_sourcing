import { computed, onBeforeUnmount, ref } from "vue";
import { useRouter } from "vue-router";
import type { RouteLocationNormalized } from "vue-router";
import { useIsMobile, usePrefersReducedMotion } from "@/composables/useViewport";

export type PageMotion = "page-forward" | "page-back" | "page-fade" | "";

const SHELL_SCROLL = '[data-slot="mobile-shell-scroll"]';

function depthOf(route: RouteLocationNormalized) {
  return route.path.split("/").filter(Boolean).length;
}

function historyPosition(): number | null {
  const position = window.history.state?.position;
  return typeof position === "number" ? position : null;
}

function motionBetween(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  position: number | null,
  lastPosition: number | null
): PageMotion {
  if (!from.matched.length) return "";

  const toDepth = depthOf(to);
  const fromDepth = depthOf(from);
  if (toDepth <= 1 && fromDepth <= 1) return "page-fade";
  if (toDepth > fromDepth) return "page-forward";
  if (toDepth < fromDepth) return "page-back";

  if (position !== null && lastPosition !== null) {
    if (position > lastPosition) return "page-forward";
    if (position < lastPosition) return "page-back";
  }
  return "page-fade";
}

export function usePageTransition() {
  const router = useRouter();
  const isMobile = useIsMobile();
  const reducedMotion = usePrefersReducedMotion();

  const motion = ref<PageMotion>("");
  let lastPosition = historyPosition();

  const stopListening = router.afterEach((to, from, failure) => {
    if (failure) return;
    const position = historyPosition();
    motion.value = motionBetween(to, from, position, lastPosition);
    lastPosition = position;
  });
  onBeforeUnmount(stopListening);

  const transitionName = computed(() =>
    isMobile.value && !reducedMotion.value ? motion.value : ""
  );

  function holdLeavingPage(element: Element) {
    const page = element as HTMLElement;
    const scroller = page.closest<HTMLElement>(SHELL_SCROLL);
    const scrolled = scroller?.scrollTop ?? 0;

    page.style.position = "absolute";
    page.style.top = `${-scrolled}px`;
    page.style.left = "0";
    page.style.width = "100%";

    if (scroller) scroller.scrollTop = 0;
  }

  return { transitionName, holdLeavingPage };
}
