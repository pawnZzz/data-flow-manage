import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"

const store = vi.hoisted(() => ({
  subgraph: { nodes: [{ id: "a", name: "a", type: "t", priority: null, is_critical: false, parent_id: null }], edges: [], stats: { node_count: 1, edge_count: 0, has_cycle: false } },
  sidebarNodes: [], selectedId: null, filters: {}, matchedIds: null,
  loadGraph: vi.fn().mockResolvedValue(undefined), select: vi.fn(), setFilter: vi.fn(), clearFilters: vi.fn(),
}))
vi.mock("@/stores/graph", () => ({ useGraphStore: () => store }))
vi.mock("@/stores/project", () => ({ useProjectStore: () => ({ can: () => true }) }))
vi.mock("@/stores/auth", () => ({ useAuthStore: () => ({ user: { id: 7 } }) }))
vi.mock("vue-router", () => ({ useRoute: () => ({ params: { pid: "1" } }) }))
vi.mock("@/api/schemas", () => ({ schemasApi: { list: vi.fn().mockResolvedValue([]) } }))
vi.mock("@/components/graph/GraphCanvas.vue", () => ({ default: { name: "GraphCanvas", template: "<div class='gc' />" } }))
vi.mock("@/components/sidebar/FilterBar.vue", () => ({ default: { name: "FilterBar", template: "<div class='fb' />" } }))
vi.mock("@/components/sidebar/NodeTree.vue", () => ({ default: { name: "NodeTree", template: "<div class='nt' />" } }))
vi.mock("@/components/graph/CreateNodeDialog.vue", () => ({ default: { name: "CreateNodeDialog", template: "<div />" } }))
vi.mock("@/components/graph/SetParentDialog.vue", () => ({ default: { name: "SetParentDialog", template: "<div />" } }))
vi.mock("@/components/graph/NodeContextMenu.vue", () => ({ default: { name: "NodeContextMenu", template: "<div />" } }))
import ElementPlus from "element-plus"
import GraphView from "@/views/GraphView.vue"

beforeEach(() => store.loadGraph.mockClear())

it("onMounted 调 loadGraph(pid) 并渲染 canvas+侧栏", async () => {
  const w = mount(GraphView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(store.loadGraph).toHaveBeenCalledWith(1)
  expect(w.find(".gc").exists()).toBe(true)
  expect(w.find(".fb").exists()).toBe(true)
  expect(w.find(".nt").exists()).toBe(true)
})
