import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"

const api = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() }))
vi.mock("@/api/schemas", () => ({ schemasApi: api }))
vi.mock("vue-router", () => ({ useRoute: () => ({ params: { pid: "1" } }) }))
const canState = vi.hoisted(() => ({ value: true }))
vi.mock("@/stores/project", () => ({ useProjectStore: () => ({ can: () => canState.value }) }))
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { success: vi.fn() }, ElMessageBox: { confirm: vi.fn().mockResolvedValue(true) } }
})

import SchemasView from "@/views/SchemasView.vue"

const SCHEMAS = [{ id: "s1", type_key: "data_task", display_name: "数据任务", fields: [], created_at: "", updated_at: "" }]

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  canState.value = true
  api.list.mockResolvedValue(SCHEMAS)
})

async function mountView() {
  const w = mount(SchemasView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

it("渲染 schema 列表", async () => {
  const w = await mountView()
  expect(w.text()).toContain("data_task")
})

it("editor 可见新建按钮", async () => {
  canState.value = true
  const w = await mountView()
  expect(w.findAll("button").some((b) => b.text() === "新建 Schema")).toBe(true)
})

it("viewer 不显示新建按钮", async () => {
  canState.value = false
  const w = await mountView()
  expect(w.findAll("button").some((b) => b.text() === "新建 Schema")).toBe(false)
})
