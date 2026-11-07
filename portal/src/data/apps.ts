import { createResource } from "frappe-ui";

export interface InstalledApp {
  name: string;
  title: string;
  logo: string | null;
  route: string;
}

export const DESK_APP: InstalledApp = {
  name: "frappe",
  title: "Desk",
  logo: "/assets/frappe/images/framework.png",
  route: "/app",
};

export const installedApps = createResource({
  url: "frappe.apps.get_apps",
  cache: "vuna-sourcing:apps",
  auto: false,
});

const THIS_APP = "vuna_sourcing";

export function appsFor(isWebsiteUser: boolean): InstalledApp[] {
  const permitted = ((installedApps.data ?? []) as InstalledApp[]).filter(
    (app) => app.name !== THIS_APP,
  );
  return isWebsiteUser ? permitted : [DESK_APP, ...permitted];
}
