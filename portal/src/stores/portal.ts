import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

import type { PartyType } from '@/data/parties'

export type { PartyType }

export interface Party {
  party_type: PartyType
  name: string
  title: string
  image: string | null
  disabled: boolean
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

export const usePortalStore = defineStore('portal', () => {
  const activePartyKey = ref<string | null>(null)

  const session = createResource({
    url: 'vuna_sourcing.api.portal.get_session',
    auto: false,
    onSuccess(data: PortalSession) {
      const keys = data.parties.map(partyKey)
      if (!activePartyKey.value || !keys.includes(activePartyKey.value)) {
        activePartyKey.value = data.parties.length ? partyKey(data.parties[0]!) : null
      }
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

  const isApplicant = computed(() => !!session.data?.is_applicant)
  const canApply = computed(() => !!session.data?.can_apply)
  const openPartyTypes = computed<PartyType[]>(() => session.data?.open_party_types ?? [])

  const partyTypesToJoin = computed<PartyType[]>(() =>
    openPartyTypes.value.filter((type) => !parties.value.some((p) => p.party_type === type)),
  )
  const hasParties = computed(() => parties.value.length > 0)
  const isMultiParty = computed(() => parties.value.length > 1)

  function setActiveParty(party: Party) {
    activePartyKey.value = partyKey(party)
  }

  function reset() {
    activePartyKey.value = null
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
    setActiveParty,
    isApplicant,
    canApply,
    openPartyTypes,
    partyTypesToJoin,
    hasParties,
    isMultiParty,
  }
})
