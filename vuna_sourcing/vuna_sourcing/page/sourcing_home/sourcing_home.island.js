import { mountVueIsland } from "@framework/ui/island";

import Page from "./sourcing_home.vue";

export const mount = (el, context) => mountVueIsland(el, { ...context, component: Page });
