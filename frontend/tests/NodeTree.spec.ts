import { it, expect } from "vitest"
import { mount } from "@vue/test-utils"
import ElementPlus from "element-plus"
import NodeTree from "@/components/sidebar/NodeTree.vue"

const N = (id: string, parent: string | null = null) => ({
  id, project_id: 1, name: id, type: "t", description: null, owner: null, department: null,
  system: null, priority: null, tags: [], ext_props: {}, is_critical: false,
  parent_id: parent, children_count: 0, upstream_count: 0, downstream_count: 0,
})

function mountTree(props: Record<string, unknown>) {
  return mount(NodeTree, { props: { matchedIds: null, ...props } as never, global: { plugins: [ElementPlus] } })
}

it("渲染父子层级", () => {
  const w = mountTree({ nodes: [N("root"), N("child", "root")] })
  expect(w.text()).toContain("root")
  expect(w.text()).toContain("child")
})

it("matchedIds 过滤只显示匹配", () => {
  const w = mountTree({ nodes: [N("a"), N("b")], matchedIds: new Set(["a"]) })
  expect(w.text()).toContain("a")
  expect(w.text()).not.toContain("b")
})

it("点击节点 emit select", async () => {
  const w = mountTree({ nodes: [N("a")] })
  await w.find(".el-tree-node__content").trigger("click")
  expect(w.emitted("select")?.[0]).toEqual(["a"])
})
