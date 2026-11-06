import { createResource } from "frappe-ui";
import type { BadgeTheme } from "@/data/application";
import type { Branch } from "@/stores/portal";
import type { ApiResponse } from "@/types/api";

export type MemberStatus = "Invited" | "Active" | "Disabled";

export const MEMBER_STATUS_THEME: Record<MemberStatus, BadgeTheme> = {
  Invited: "amber",
  Active: "green",
  Disabled: "gray",
};

export interface TeamMember {
  user: string;
  full_name: string;
  image: string | null;
  is_account_admin: boolean;
  is_you: boolean;
  status: MemberStatus;
  all_branches: boolean;
  branches: Branch[];
  editable: boolean;
}

export interface Team {
  customer: string;
  members: TeamMember[];
}

export interface InvitePayload {
  first_name: string;
  last_name: string;
  email: string;
  branches: string[];
}

const TEAM = "vuna_sourcing.api.transactions.team";

function createTeamResource(user: string, customer: string) {
  return createResource({
    url: `${TEAM}.get_team`,
    params: { customer },
    cache: ["vuna-sourcing:team", user, customer],
    auto: false,
  });
}

const teamResources = new Map<string, ReturnType<typeof createTeamResource>>();

export function teamResource(user: string, customer: string) {
  const key = `${user}::${customer}`;
  let resource = teamResources.get(key);
  if (!resource) {
    resource = createTeamResource(user, customer);
    teamResources.set(key, resource);
  }
  return resource;
}

function post<T>(method: string, payload: object): Promise<ApiResponse<T>> {
  return createResource({ url: `${TEAM}.${method}`, method: "POST" }).submit(payload);
}

export function inviteMember(customer: string, payload: InvitePayload) {
  return post<{ members: TeamMember[] }>("invite_team_member", { customer, ...payload });
}

export function updateMemberBranches(customer: string, user: string, branches: string[]) {
  return post<{ members: TeamMember[] }>("update_member_branches", { customer, user, branches });
}

export function removeMember(customer: string, user: string) {
  return post<{ members: TeamMember[] }>("remove_team_member", { customer, user });
}

export function resendInvitation(customer: string, user: string) {
  return post<null>("resend_invitation", { customer, user });
}

export function branchSummary(member: Pick<TeamMember, "all_branches" | "branches">) {
  if (member.all_branches) return "All branches";
  if (member.branches.length === 1) return member.branches[0]!.title;
  return `${member.branches.length} branches`;
}
