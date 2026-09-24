import { useRoute, useRouter } from "vue-router";
import { usePortalStore } from "@/stores/portal";
import type { Party, PartyType } from "@/stores/portal";

export function usePartySwitch() {
	const portal = usePortalStore();
	const route = useRoute();
	const router = useRouter();

	function leaveIfForeign(type: PartyType) {
		const needed = route.meta.partyType;
		if (needed && needed !== type) router.push({ name: "PortalOverview" });
	}

	function setActiveParty(party: Party) {
		portal.setActiveParty(party);
		leaveIfForeign(party.party_type);
	}

	function switchToType(type: PartyType) {
		portal.switchToType(type);
		leaveIfForeign(type);
	}

	return { setActiveParty, switchToType };
}
