import { it, expect } from "vitest"
import { dagre } from "@/components/graph/layout"

const N = (id: string) => ({ id, name: id, type: "t", priority: null, is_critical: false, parent_id: null })
const E = (s: string, t: string) => ({
  id: `${s}-${t}`, project_id: 1, source_id: s, target_id: t, edge_type: "data_flow",
  description: null, is_required: true, strength: "strong", ext_props: {}, created_at: "", created_by: 1,
})

it("空图返回空位置", async () => {
  expect(await dagre([], [])).toEqual({})
})

it("每个节点都有非 NaN 坐标", async () => {
  const pos = await dagre([N("a"), N("b"), N("c")], [E("a", "b"), E("b", "c")])
  for (const id of ["a", "b", "c"]) {
    expect(pos[id]).toBeDefined()
    expect(Number.isFinite(pos[id].x)).toBe(true)
    expect(Number.isFinite(pos[id].y)).toBe(true)
  }
})

it("分层：下游节点 y 大于上游（TB）", async () => {
  const pos = await dagre([N("a"), N("b")], [E("a", "b")])
  expect(pos.b.y).toBeGreaterThan(pos.a.y)
})
