import { computed, ref } from "vue"
import { defineStore } from "pinia"
import { graphApi } from "@/api/graph"
import { nodesApi } from "@/api/nodes"
import type { NodeFilters, NodeResponse, Subgraph } from "@/types/graph"

export const useGraphStore = defineStore("graph", () => {
  const subgraph = ref<Subgraph | null>(null)
  const sidebarNodes = ref<NodeResponse[]>([])
  const selectedId = ref<string | null>(null)
  const filters = ref<NodeFilters>({})

  const hasFilter = computed(() =>
    Object.values(filters.value).some((v) => v !== undefined && v !== ""),
  )

  function nodeMatches(n: NodeResponse, f: NodeFilters): boolean {
    if (f.type && n.type !== f.type) return false
    if (f.department && n.department !== f.department) return false
    if (f.system && n.system !== f.system) return false
    if (f.priority && n.priority !== f.priority) return false
    if (f.tag && !n.tags.includes(f.tag)) return false
    if (f.name && !n.name.toLowerCase().includes(f.name.toLowerCase())) return false
    return true
  }

  const matchedIds = computed<Set<string> | null>(() => {
    if (!hasFilter.value) return null
    const ids = new Set<string>()
    for (const n of sidebarNodes.value) {
      if (nodeMatches(n, filters.value)) ids.add(n.id)
    }
    return ids
  })

  async function loadGraph(pid: number) {
    const [sg, nodes] = await Promise.all([graphApi.getSubgraph(pid), nodesApi.list(pid)])
    subgraph.value = sg
    sidebarNodes.value = nodes
  }

  function select(id: string | null) {
    selectedId.value = id
  }
  function setFilter(patch: Partial<NodeFilters>) {
    filters.value = { ...filters.value, ...patch }
  }
  function clearFilters() {
    filters.value = {}
  }
  function clear() {
    subgraph.value = null
    sidebarNodes.value = []
    selectedId.value = null
    filters.value = {}
  }

  return {
    subgraph, sidebarNodes, selectedId, filters,
    matchedIds, loadGraph, select, setFilter, clearFilters, clear,
  }
})
