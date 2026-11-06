import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

import { PARTY_TYPES } from '@/data/parties'
import type { PartyType } from '@/data/parties'

export type { PartyType }

export interface Branch {
  name: string
  title: string
}

export interface BranchScope {
  all_branches: boolean
  branches: Branch[]
}

export interface Party {
  party_type: PartyType
  name: string
  title: string
  image: string | null
  disabled: boolean
  all_branches?: boolean
  can_manage_team?: boolean
}

function createBranchesResource(user: string, customer: string) {
  return createResource({
    url: 'vuna_sourcing.api.transactions.branches.get_branches',
    params: { customer },
    cache: ['vuna-sourcing:branches', user, customer],
    auto: true,
  })
}

const branchResources = new Map<string, ReturnType<typeof createBranchesResource>>()

function branchesResource(user: string, customer: string) {
  const key = `${user}::${customer}`
  let resource = branchResources.get(key)
  if (!resource) {
    resource = createBranchesResource(user, customer)
    branchResources.set(key, resource)
  }
  return resource
}

export interface PortalUser {
  name: string
  full_name: string
  email: string
  image: string | null
  is_website_user: boolean
}

export interface PortalSession {
  user: PortalUser
  parties: Party[]
  roles: string[]
  open_party_types: PartyType[]
  can_apply: boolean
  is_applicant: boolean
}

export function partyKey(party: Pick<Party, 'party_type' | 'name'>) {
  return `${party.party_type}::${party.name}`
}

export function initials(text: string) {
  return (text || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]!.toUpperCase())
    .join('')
}

function recallKey(email: string) {
  return `vuna-sourcing:last-party:${email}`
}

function recall(email: string): string | null {
  try {
    return window.localStorage.getItem(recallKey(email))
  } catch {
    return null
  }
}

function remember(email: string, key: string) {
  try {
    window.localStorage.setItem(recallKey(email), key)
  } catch {
    return
  }
}

export const usePortalStore = defineStore('portal', () => {
  const activePartyKey = ref<string | null>(null)

  const lastKeyByType = ref<Partial<Record<PartyType, string>>>({})

  const branchesByParty = ref<Record<string, string[]>>({})

  const session = createResource({
    url: 'vuna_sourcing.api.portal.get_session',
    auto: false,
    onSuccess(data: PortalSession) {
      const keys = data.parties.map(partyKey)
      if (!activePartyKey.value || !keys.includes(activePartyKey.value)) {
        const remembered = recall(data.user.email)
        activePartyKey.value =
          remembered && keys.includes(remembered)
            ? remembered
            : data.parties.length
              ? partyKey(data.parties[0]!)
              : null
      }
      for (const party of data.parties) {
        lastKeyByType.value[party.party_type] ??= partyKey(party)
      }
      const active = data.parties.find((p) => partyKey(p) === activePartyKey.value)
      if (active) lastKeyByType.value[active.party_type] = partyKey(active)
    },
  })

  const user = computed<PortalUser | null>(() => session.data?.user ?? null)
  const parties = computed<Party[]>(() => session.data?.parties ?? [])
  const roles = computed<string[]>(() => session.data?.roles ?? [])

  const suppliers = computed(() => parties.value.filter((p) => p.party_type === 'Supplier'))
  const customers = computed(() => parties.value.filter((p) => p.party_type === 'Customer'))

  const activeParty = computed<Party | null>(() => {
    const list = parties.value
    if (!list.length) return null
    return list.find((p) => partyKey(p) === activePartyKey.value) ?? list[0]!
  })

  const branchList = computed(() => {
    const party = activeParty.value
    const email = user.value?.name
    return party?.party_type === 'Customer' && email ? branchesResource(email, party.name) : null
  })

  const activeBranches = computed<Branch[]>(
    () => (branchList.value?.data?.data as BranchScope | undefined)?.branches ?? [],
  )

  const branchesLoading = computed(
    () => !!branchList.value?.loading && !branchList.value?.data,
  )

  const selectedBranches = computed<string[]>(() =>
    activeParty.value ? (branchesByParty.value[partyKey(activeParty.value)] ?? []) : [],
  )

  const branchFilter = computed<string[] | null>(() =>
    selectedBranches.value.length ? selectedBranches.value : null,
  )

  function setSelectedBranches(names: string[]) {
    if (!activeParty.value) return
    branchesByParty.value = { ...branchesByParty.value, [partyKey(activeParty.value)]: names }
  }

  const isBranchLimited = computed(
    () => activeParty.value?.party_type === 'Customer' && activeParty.value.all_branches === false,
  )

  const canManageTeam = computed(
    () => activeParty.value?.party_type === 'Customer' && !!activeParty.value.can_manage_team,
  )

  const seesAnyStatement = computed(() =>
    customers.value.some((customer) => customer.all_branches !== false),
  )

  const isApplicant = computed(() => !!session.data?.is_applicant)
  const canApply = computed(() => !!session.data?.can_apply)
  const openPartyTypes = computed<PartyType[]>(() => session.data?.open_party_types ?? [])

  const partyTypesToJoin = computed<PartyType[]>(() =>
    openPartyTypes.value.filter((type) => !parties.value.some((p) => p.party_type === type)),
  )
  const hasParties = computed(() => parties.value.length > 0)
  const isMultiParty = computed(() => parties.value.length > 1)

  const partyTypesJoined = computed<PartyType[]>(() =>
    PARTY_TYPES.filter((type) => parties.value.some((p) => p.party_type === type)),
  )

  function partiesOfType(type: PartyType) {
    return parties.value.filter((p) => p.party_type === type)
  }

  const activeSiblings = computed(() =>
    activeParty.value ? partiesOfType(activeParty.value.party_type) : [],
  )

  function setActiveParty(party: Party) {
    activePartyKey.value = partyKey(party)
    lastKeyByType.value[party.party_type] = partyKey(party)
    const email = user.value?.email
    if (email) remember(email, partyKey(party))
  }

  function switchToType(type: PartyType) {
    const candidates = partiesOfType(type)
    if (!candidates.length) return
    const remembered = candidates.find((p) => partyKey(p) === lastKeyByType.value[type])
    setActiveParty(remembered ?? candidates[0]!)
  }

  function reset() {
    activePartyKey.value = null
    branchesByParty.value = {}
    session.reset()
  }

  async function load() {
    if (session.data) return session.data
    return session.fetch()
  }

  return {
    session,
    load,
    reset,
    user,
    roles,
    parties,
    suppliers,
    customers,
    activeParty,
    activePartyKey,
    activeSiblings,
    partyTypesJoined,
    partiesOfType,
    setActiveParty,
    switchToType,
    isApplicant,
    canApply,
    openPartyTypes,
    partyTypesToJoin,
    hasParties,
    isMultiParty,
    activeBranches,
    branchesLoading,
    selectedBranches,
    branchFilter,
    setSelectedBranches,
    isBranchLimited,
    canManageTeam,
    seesAnyStatement,
  }
})
