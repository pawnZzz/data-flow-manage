import { it, expect } from "vitest"
import { mount } from "@vue/test-utils"
import NodeContextMenu from "@/components/graph/NodeContextMenu.vue"

function mountMenu(props = {}) {
  return mount(NodeContextMenu, { props: { visible: true, x: 10, y: 20, kind: "node", ...props } })
}

it("node kind 显示删除/设父/解父", () => {
  const w = mountMenu({ kind: "node" })
  const txt = w.text()
  expect(txt).toContain("删除节点")
  expect(txt).toContain("设父节点")
  expect(txt).toContain("解除父")
})

it("edge kind 只显示删除边", () => {
  const w = mountMenu({ kind: "edge" })
  expect(w.text()).toContain("删除边")
  expect(w.text()).not.toContain("设父节点")
})

it("visible=false 不渲染", () => {
  const w = mountMenu({ visible: false })
  expect(w.find(".ctx-menu").exists()).toBe(false)
})

it("点删除 emit delete", async () => {
  const w = mountMenu({ kind: "node" })
  await w.findAll("li").find((li) => li.text() === "删除节点")!.trigger("click")
  expect(w.emitted("delete")).toBeTruthy()
})

it("点设父 emit setParent", async () => {
  const w = mountMenu({ kind: "node" })
  await w.findAll("li").find((li) => li.text() === "设父节点")!.trigger("click")
  expect(w.emitted("setParent")).toBeTruthy()
})
