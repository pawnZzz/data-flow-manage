import { it, expect } from "vitest"
import { mount } from "@vue/test-utils"
import ElementPlus from "element-plus"
import FilterBar from "@/components/sidebar/FilterBar.vue"

const NODES = [
  { id: "a", project_id: 1, name: "a", type: "data_task", description: null, owner: null, department: null, system: null, priority: null, tags: [], ext_props: {}, is_critical: false, parent_id: null, children_count: 0, upstream_count: 0, downstream_count: 0 },
  { id: "b", project_id: 1, name: "b", type: "service", description: null, owner: null, department: null, system: null, priority: null, tags: [], ext_props: {}, is_critical: false, parent_id: null, children_count: 0, upstream_count: 0, downstream_count: 0 },
]

function mountBar() {
  return mount(FilterBar, { props: { filters: {}, nodes: NODES }, global: { plugins: [ElementPlus] } })
}

it("name 输入 emit setFilter", async () => {
  const w = mountBar()
  await w.find("input").setValue("alpha")
  const e = w.emitted("setFilter")
  expect(e).toBeTruthy()
  expect(e![e!.length - 1][0]).toEqual({ name: "alpha" })
})

it("清空 emit clear", async () => {
  const w = mountBar()
  await w.findAll("button").find((b) => b.text() === "清空")!.trigger("click")
  expect(w.emitted("clear")).toBeTruthy()
})
