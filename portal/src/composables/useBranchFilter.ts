import { computed } from "vue";
import { usePortalStore } from "@/stores/portal";

export function useBranchFilter() {
	const portal = usePortalStore();

	const titles = computed(
		() => new Map(portal.activeBranches.map((branch) => [branch.name, branch.title]))
	);
	const showBranch = computed(() => portal.activeBranches.length > 1);
	const branchFilter = computed(() => portal.branchFilter);

	function branchTitle(name: string | null | undefined) {
		return name ? (titles.value.get(name) ?? name) : "";
	}

	function clearBranches() {
		portal.setSelectedBranches([]);
	}

	return { branchFilter, showBranch, branchTitle, clearBranches };
}

<<<<<<< HEAD
export const BRANCH_COLUMN = { label: "Branch", key: "branch", width: "minmax(120px, 1fr)" };
=======
export const BRANCH_COLUMN = { label: "Branch", key: "branch", width: "180px" };
>>>>>>> 8cb49e9 (feat(sourcing): customer branches and account-admin team management on the portal)

export function withBranchColumn<T>(columns: T[], show: boolean): Array<T | typeof BRANCH_COLUMN> {
	if (!show || !columns.length) return columns;
	return [...columns.slice(0, -1), BRANCH_COLUMN, columns[columns.length - 1]];
}
