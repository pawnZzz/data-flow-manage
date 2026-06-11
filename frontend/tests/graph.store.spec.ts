import { it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"

const graphApi = vi.hoisted(() => ({ getSubgraph: vi.fn() }))
const nodesApi = vi.hoisted(() => ({ list: vi.fn() }))
vi.mock("@/api/graph", () => ({ graphApi }))
vi.mock("@/api/nodes", () => ({ nodesApi }))

import { useGraphStore } from "@/stores/graph"

const SG = { nodes: [{ id: "a", name: "a", type: "t", priority: null, is_critical: false, parent_id: null }], edges: [], stats: { node_count: 1, edge_count: 0, has_cycle: false } }
const NODES = [
  { id: "a", project_id: 1, name: "alpha", type: "data_task", description: null, owner: null, department: "dw", system: null, priority: "P1", tags: ["core"], ext_props: {}, is_critical: false, parent_id: null, children_count: 0, upstream_count: 0, downstream_count: 0 },
  { id: "b", project_id: 1, name: "beta", type: "service", description: null, owner: null, department: "ops", system: null, priority: "P3", tags: [], ext_props: {}, is_critical: false, parent_id: null, children_count: 0, upstream_count: 0, downstream_count: 0 },
]

beforeEach(() => {
  setActivePinia(createPinia())
  graphApi.getSubgraph.mockReset()
  nodesApi.list.mockReset()
})

it("loadGraph 并发填 subgraph + sidebarNodes", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  expect(s.subgraph?.nodes.length).toBe(1)
  expect(s.sidebarNodes.length).toBe(2)
})

it("无 filter 时 matchedIds 为 null（全亮）", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  expect(s.matchedIds).toBeNull()
})

it("按 type 过滤算 matchedIds", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  s.setFilter({ type: "data_task" })
  expect([...(s.matchedIds as Set<string>)]).toEqual(["a"])
})

it("按 name 子串 + tag + department 过滤", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  s.setFilter({ name: "ALP" })
  expect([...(s.matchedIds as Set<string>)]).toEqual(["a"])
  s.clearFilters()
  s.setFilter({ tag: "core" })
  expect([...(s.matchedIds as Set<string>)]).toEqual(["a"])
  s.clearFilters()
  s.setFilter({ department: "ops" })
  expect([...(s.matchedIds as Set<string>)]).toEqual(["b"])
})

it("select / clear", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  s.select("a")
  expect(s.selectedId).toBe("a")
  s.clear()
  expect(s.subgraph).toBeNull()
  expect(s.selectedId).toBeNull()
})
