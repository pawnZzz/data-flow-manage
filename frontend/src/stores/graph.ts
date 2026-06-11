import { computed, ref } from "vue"
import { defineStore } from "pinia"
import { graphApi } from "@/api/graph"
import { nodesApi } from "@/api/nodes"
import { edgesApi } from "@/api/edges"
import type { NodeFilters, NodeResponse, Subgraph } from "@/types/graph"

export const useGraphStore = defineStore("graph", () => {
  const subgraph = ref<Subgraph | null>(null)
  const sidebarNodes = ref<NodeResponse[]>([])
  const selectedId = ref<string | null>(null)
  const filters = ref<NodeFilters>({})
  const currentPid = ref<number | null>(null)

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
    currentPid.value = pid
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
  function pid(): number {
    if (currentPid.value === null) throw new Error("no current project loaded")
    return currentPid.value
  }

  async function createNode(body: { name: string; type: string }) {
    const node = await nodesApi.create(pid(), body)
    await loadGraph(pid())
    return node
  }
  async function deleteNode(nid: string) {
    await nodesApi.remove(pid(), nid)
    await loadGraph(pid())
  }
  async function createEdge(body: { source_id: string; target_id: string; edge_type?: string }) {
    const res = await edgesApi.create(pid(), body)
    await loadGraph(pid())
    return res
  }
  async function deleteEdge(eid: string) {
    await edgesApi.remove(pid(), eid)
    await loadGraph(pid())
  }
  async function setParent(nid: string, parentId: string) {
    await nodesApi.setParent(pid(), nid, parentId)
    await loadGraph(pid())
  }
  async function clearParent(nid: string) {
    await nodesApi.clearParent(pid(), nid)
    await loadGraph(pid())
  }

  function clear() {
    subgraph.value = null
    sidebarNodes.value = []
    selectedId.value = null
    filters.value = {}
    currentPid.value = null
  }

  return {
    subgraph, sidebarNodes, selectedId, filters, currentPid,
    matchedIds, loadGraph, select, setFilter, clearFilters, clear,
    createNode, deleteNode, createEdge, deleteEdge, setParent, clearParent,
  }
})
