import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"

const calls = vi.hoisted(() => ({
  init: vi.fn(), setData: vi.fn(), applyPositions: vi.fn(), runLayout: vi.fn().mockResolvedValue({}),
  highlightSelected: vi.fn(), applyMatch: vi.fn(), centerOn: vi.fn(),
  onNodeClick: vi.fn(), onNodeMoved: vi.fn(), dispose: vi.fn(),
  setEditable: vi.fn(), onEdgeConnected: vi.fn(), removeEdgeCell: vi.fn(),
  onNodeContextmenu: vi.fn(), onEdgeContextmenu: vi.fn(),
}))
vi.mock("@/components/graph/graphController", () => ({
  GraphController: vi.fn(() => calls),
}))

import GraphCanvas from "@/components/graph/GraphCanvas.vue"

const SG = {
  nodes: [{ id: "a", name: "a", type: "t", priority: null, is_critical: false, parent_id: null }],
  edges: [], stats: { node_count: 1, edge_count: 0, has_cycle: false },
}

beforeEach(() => {
  Object.values(calls).forEach((f) => (f as any).mockReset?.())
  calls.runLayout.mockResolvedValue({})
})

function mountCanvas(props = {}) {
  return mount(GraphCanvas, {
    props: { subgraph: SG, matchedIds: null, selectedId: null, savedPositions: {}, editable: false, ...props },
    attachTo: document.body,
  })
}

it("挂载 init + setData，无持久位置时 runLayout", async () => {
  mountCanvas()
  await flushPromises()
  expect(calls.init).toHaveBeenCalled()
  expect(calls.setData).toHaveBeenCalled()
  expect(calls.runLayout).toHaveBeenCalled()
  expect(calls.applyPositions).not.toHaveBeenCalled()
})

it("有持久位置时 applyPositions 而非 runLayout", async () => {
  mountCanvas({ savedPositions: { a: { x: 1, y: 2 } } })
  await flushPromises()
  expect(calls.applyPositions).toHaveBeenCalledWith({ a: { x: 1, y: 2 } })
  expect(calls.runLayout).not.toHaveBeenCalled()
})

it("node:click 经回调 emit select", async () => {
  const w = mountCanvas()
  await flushPromises()
  const cb = calls.onNodeClick.mock.calls[0][0] as (id: string) => void
  cb("a")
  expect(w.emitted("select")?.[0]).toEqual(["a"])
})

it("matchedIds 变化触发 applyMatch", async () => {
  const w = mountCanvas()
  await flushPromises()
  calls.applyMatch.mockReset()
  await w.setProps({ matchedIds: new Set(["a"]) })
  expect(calls.applyMatch).toHaveBeenCalledWith(new Set(["a"]))
})

it("卸载 dispose", async () => {
  const w = mountCanvas()
  await flushPromises()
  w.unmount()
  expect(calls.dispose).toHaveBeenCalled()
})

it("editable=true 时 setEditable(true) 并注册编辑回调", async () => {
  mountCanvas({ editable: true })
  await flushPromises()
  expect(calls.setEditable).toHaveBeenCalledWith(true)
  expect(calls.onEdgeConnected).toHaveBeenCalled()
  expect(calls.onNodeContextmenu).toHaveBeenCalled()
  expect(calls.onEdgeContextmenu).toHaveBeenCalled()
})

it("editable=false 时 setEditable(false)", async () => {
  mountCanvas({ editable: false })
  await flushPromises()
  expect(calls.setEditable).toHaveBeenCalledWith(false)
})

it("edge:connected 回调先 removeEdgeCell 再 emit edgeConnected", async () => {
  const w = mountCanvas({ editable: true })
  await flushPromises()
  const cb = calls.onEdgeConnected.mock.calls[0][0] as (s: string, t: string, id: string) => void
  cb("a", "b", "tmpEdge")
  expect(calls.removeEdgeCell).toHaveBeenCalledWith("tmpEdge")
  expect(w.emitted("edgeConnected")?.[0]).toEqual(["a", "b", "tmpEdge"])
})
