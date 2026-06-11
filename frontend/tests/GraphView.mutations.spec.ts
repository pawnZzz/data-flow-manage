import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"

const store = vi.hoisted(() => ({
  subgraph: { nodes: [{ id: "a", name: "a", type: "t", priority: null, is_critical: false, parent_id: null }], edges: [], stats: { node_count: 1, edge_count: 0, has_cycle: false } },
  sidebarNodes: [{ id: "a", name: "a" }, { id: "b", name: "b" }], selectedId: null, filters: {}, matchedIds: null,
  loadGraph: vi.fn().mockResolvedValue(undefined), select: vi.fn(), setFilter: vi.fn(), clearFilters: vi.fn(),
  createNode: vi.fn().mockResolvedValue({}), deleteNode: vi.fn().mockResolvedValue(undefined),
  createEdge: vi.fn().mockResolvedValue({ edge: {}, warnings: { creates_cycle: false } }),
  deleteEdge: vi.fn().mockResolvedValue(undefined), setParent: vi.fn().mockResolvedValue(undefined), clearParent: vi.fn().mockResolvedValue(undefined),
}))
const canEditor = vi.hoisted(() => ({ value: true }))
vi.mock("@/stores/graph", () => ({ useGraphStore: () => store }))
vi.mock("@/stores/project", () => ({ useProjectStore: () => ({ can: () => canEditor.value }) }))
vi.mock("@/stores/auth", () => ({ useAuthStore: () => ({ user: { id: 7 } }) }))
vi.mock("vue-router", () => ({ useRoute: () => ({ params: { pid: "1" } }) }))
vi.mock("@/api/schemas", () => ({ schemasApi: { list: vi.fn().mockResolvedValue([]) } }))
vi.mock("@/components/graph/GraphCanvas.vue", () => ({ default: { name: "GraphCanvas", template: "<div class='gc' />" } }))
vi.mock("@/components/sidebar/FilterBar.vue", () => ({ default: { name: "FilterBar", template: "<div />" } }))
vi.mock("@/components/sidebar/NodeTree.vue", () => ({ default: { name: "NodeTree", template: "<div />" } }))
vi.mock("@/components/graph/CreateNodeDialog.vue", () => ({ default: { name: "CreateNodeDialog", template: "<div />" } }))
vi.mock("@/components/graph/SetParentDialog.vue", () => ({ default: { name: "SetParentDialog", template: "<div />" } }))
vi.mock("@/components/graph/NodeContextMenu.vue", () => ({ default: { name: "NodeContextMenu", props: ["visible", "x", "y", "kind"], template: "<div />" } }))
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { success: vi.fn(), warning: vi.fn() }, ElMessageBox: { confirm: vi.fn().mockResolvedValue(true) } }
})

import ElementPlus from "element-plus"
import GraphView from "@/views/GraphView.vue"

function mountView() {
  return mount(GraphView, { global: { plugins: [ElementPlus] } })
}

beforeEach(() => { canEditor.value = true; Object.values(store).forEach((f) => (f as any)?.mockClear?.()) })

it("editor 显示新建节点按钮", async () => {
  const w = mountView(); await flushPromises()
  expect(w.findAll("button").some((b) => b.text() === "新建节点")).toBe(true)
})

it("viewer 不显示新建节点", async () => {
  canEditor.value = false
  const w = mountView(); await flushPromises()
  expect(w.findAll("button").some((b) => b.text() === "新建节点")).toBe(false)
})

it("edgeConnected 调 store.createEdge", async () => {
  const w = mountView(); await flushPromises()
  w.findComponent({ name: "GraphCanvas" }).vm.$emit("edgeConnected", "a", "b", "tmp")
  await flushPromises()
  expect(store.createEdge).toHaveBeenCalledWith({ source_id: "a", target_id: "b" })
})

it("nodeContextmenu→删除 走 confirm 调 store.deleteNode", async () => {
  const w = mountView(); await flushPromises()
  w.findComponent({ name: "GraphCanvas" }).vm.$emit("nodeContextmenu", "a", 5, 6)
  await flushPromises()
  w.findComponent({ name: "NodeContextMenu" }).vm.$emit("delete")
  await flushPromises()
  expect(store.deleteNode).toHaveBeenCalledWith("a")
})

it("viewer 右键不打开编辑菜单", async () => {
  canEditor.value = false
  const w = mountView(); await flushPromises()
  w.findComponent({ name: "GraphCanvas" }).vm.$emit("nodeContextmenu", "a", 5, 6)
  await flushPromises()
  expect(w.findComponent({ name: "NodeContextMenu" }).props("visible")).toBe(false)
})
