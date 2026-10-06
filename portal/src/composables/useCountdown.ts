import { computed, onBeforeUnmount, ref, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function useCountdown(until: MaybeRefOrGetter<string | null | undefined>) {
  const now = ref(Date.now());
  const timer = setInterval(() => (now.value = Date.now()), SECOND);
  onBeforeUnmount(() => clearInterval(timer));

  const remaining = computed(() => {
    const target = toValue(until);
    if (!target) return null;
    return Math.max(new Date(target).getTime() - now.value, 0);
  });

  const label = computed(() => {
    const ms = remaining.value;
    if (ms === null) return "—";
    if (ms === 0) return "Closed";

    const days = Math.floor(ms / DAY);
    const hours = Math.floor((ms % DAY) / HOUR);
    const minutes = Math.floor((ms % HOUR) / MINUTE);
    const seconds = Math.floor((ms % MINUTE) / SECOND);
    const pad = (value: number) => String(value).padStart(2, "0");

    if (days) return `${days}d ${hours}h ${pad(minutes)}m`;
    return `${hours ? `${hours}h ` : ""}${pad(minutes)}m ${pad(seconds)}s`;
  });

  const ended = computed(() => remaining.value === 0);
  const urgent = computed(() => remaining.value !== null && remaining.value < HOUR);

  return { remaining, label, ended, urgent };
}
