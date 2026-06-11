import { it, expect } from "vitest"
import { colorForType, toXNode } from "@/components/graph/nodeShapes"

const NODE = { id: "n1", name: "ods", type: "data_task", priority: "P1", is_critical: false, parent_id: null }

it("colorForType 同 type 稳定同色", () => {
  expect(colorForType("data_task")).toBe(colorForType("data_task"))
})

it("colorForType 取自调色板（# 开头）", () => {
  expect(colorForType("service").startsWith("#")).toBe(true)
})

it("toXNode label 含 name 与 priority", () => {
  expect(toXNode(NODE).label).toBe("ods [P1]")
  expect(toXNode(NODE).id).toBe("n1")
})

it("toXNode 无 priority 时 label 只 name", () => {
  expect(toXNode({ ...NODE, priority: null }).label).toBe("ods")
})

it("is_critical 加红描边加粗", () => {
  const x = toXNode({ ...NODE, is_critical: true })
  expect(x.attrs.body.stroke).toBe("#F5222D")
  expect(x.attrs.body.strokeWidth).toBe(3)
})

it("toXNode 套用传入位置", () => {
  const x = toXNode(NODE, { x: 10, y: 20 })
  expect([x.x, x.y]).toEqual([10, 20])
})
