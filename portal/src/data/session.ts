import { computed, reactive, ref } from "vue";
import { createResource } from "frappe-ui";

export const BASE_PATH = "/vuna-sourcing";

export function loginUrl(fullPath = "/") {
  return `/login?redirect-to=${encodeURIComponent(BASE_PATH + fullPath)}`;
}

export function sessionUser(): string | null {
  const cookies = new URLSearchParams(document.cookie.split("; ").join("&"));
  const user = cookies.get("user_id");
  return !user || user === "Guest" ? null : decodeURIComponent(user);
}

const currentUser = ref<string | null>(sessionUser());

export const session = reactive({
  user: currentUser,
  isLoggedIn: computed(() => !!currentUser.value),

  logout: createResource({
    url: "logout",
    onSuccess() {
      currentUser.value = null;
      window.location.href = loginUrl();
    },
  }),
});
