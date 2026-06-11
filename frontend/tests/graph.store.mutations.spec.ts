import { it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"

const graphApi = vi.hoisted(() => ({ getSubgraph: vi.fn() }))
const nodesApi = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), remove: vi.fn(), setParent: vi.fn(), clearParent: vi.fn() }))
const edgesApi = vi.hoisted(() => ({ create: vi.fn(), remove: vi.fn() }))
vi.mock("@/api/graph", () => ({ graphApi }))
vi.mock("@/api/nodes", () => ({ nodesApi }))
vi.mock("@/api/edges", () => ({ edgesApi }))

import { useGraphStore } from "@/stores/graph"

const SG = { nodes: [], edges: [], stats: { node_count: 0, edge_count: 0, has_cycle: false } }

beforeEach(() => {
  setActivePinia(createPinia())
  ;[graphApi.getSubgraph, nodesApi.list, nodesApi.create, nodesApi.remove, nodesApi.setParent, nodesApi.clearParent, edgesApi.create, edgesApi.remove].forEach((f) => f.mockReset())
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue([])
})

async function loaded() {
  const s = useGraphStore()
  await s.loadGraph(7)
  graphApi.getSubgraph.mockClear()
  nodesApi.list.mockClear()
  return s
}

it("createNode 调 api 并重拉", async () => {
  const s = await loaded()
  nodesApi.create.mockResolvedValue({ id: "n" })
  await s.createNode({ name: "x", type: "t" })
  expect(nodesApi.create).toHaveBeenCalledWith(7, { name: "x", type: "t" })
  expect(graphApi.getSubgraph).toHaveBeenCalledWith(7)
})

it("createEdge 调 api、重拉并透传 warnings", async () => {
  const s = await loaded()
  edgesApi.create.mockResolvedValue({ edge: { id: "e" }, warnings: { creates_cycle: true } })
  const res = await s.createEdge({ source_id: "a", target_id: "b" })
  expect(edgesApi.create).toHaveBeenCalledWith(7, { source_id: "a", target_id: "b" })
  expect(res.warnings.creates_cycle).toBe(true)
  expect(graphApi.getSubgraph).toHaveBeenCalledWith(7)
})

it("deleteNode/deleteEdge/setParent/clearParent 调 api 并重拉", async () => {
  const s = await loaded()
  nodesApi.remove.mockResolvedValue(undefined)
  edgesApi.remove.mockResolvedValue(undefined)
  nodesApi.setParent.mockResolvedValue(undefined)
  nodesApi.clearParent.mockResolvedValue(undefined)
  await s.deleteNode("n")
  await s.deleteEdge("e")
  await s.setParent("c", "p")
  await s.clearParent("c")
  expect(nodesApi.remove).toHaveBeenCalledWith(7, "n")
  expect(edgesApi.remove).toHaveBeenCalledWith(7, "e")
  expect(nodesApi.setParent).toHaveBeenCalledWith(7, "c", "p")
  expect(nodesApi.clearParent).toHaveBeenCalledWith(7, "c")
  expect(graphApi.getSubgraph).toHaveBeenCalledTimes(4)
})

it("api 抛错时不重拉、错误冒泡", async () => {
  const s = await loaded()
  nodesApi.create.mockRejectedValue(new Error("409"))
  await expect(s.createNode({ name: "x", type: "t" })).rejects.toThrow()
  expect(graphApi.getSubgraph).not.toHaveBeenCalled()
})
