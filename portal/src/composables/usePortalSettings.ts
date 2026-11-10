import { ref } from "vue";

export type SettingsTab = "profile" | "team" | "credit" | "preferences";

const open = ref(false);
const tab = ref<SettingsTab>("profile");

export function usePortalSettings() {
  function show(target: SettingsTab = "profile") {
    tab.value = target;
    open.value = true;
  }

  return { open, tab, show };
}
