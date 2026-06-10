import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"

const api = vi.hoisted(() => ({
  list: vi.fn(), create: vi.fn(), update: vi.fn(),
  archive: vi.fn(), unarchive: vi.fn(), purge: vi.fn(),
}))
vi.mock("@/api/projects", () => ({ projectsApi: api }))
const push = vi.fn()
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }))
const confirm = vi.fn()
const prompt = vi.fn()
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { success: vi.fn(), error: vi.fn() }, ElMessageBox: { confirm: (...a: unknown[]) => confirm(...a), prompt: (...a: unknown[]) => prompt(...a) } }
})

import ProjectListView from "@/views/ProjectListView.vue"

const ACTIVE = { id: 1, name: "Alpha", description: null, status: "active", created_by: 1, my_role: "owner" }
const ARCHIVED = { id: 2, name: "Beta", description: null, status: "archived", created_by: 1, my_role: "owner" }

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  push.mockReset(); confirm.mockReset(); prompt.mockReset()
  api.list.mockResolvedValue([ACTIVE])
})

async function mountView() {
  const w = mount(ProjectListView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

it("挂载即拉取项目列表", async () => {
  const w = await mountView()
  expect(api.list).toHaveBeenCalledWith(false)
  expect(w.text()).toContain("Alpha")
})

it("显示归档切换重拉 list(true)", async () => {
  const w = await mountView()
  await w.findComponent({ name: "ElSwitch" }).find("input").setValue(true)
  await flushPromises()
  expect(api.list).toHaveBeenCalledWith(true)
})

it("purge 输错名不调用 purge", async () => {
  api.list.mockResolvedValue([ARCHIVED])
  prompt.mockResolvedValue({ value: "WRONG" })
  const w = await mountView()
  await w.findAll("button").find((b) => b.text() === "永久删除")!.trigger("click")
  await flushPromises()
  expect(api.purge).not.toHaveBeenCalled()
})

it("purge 输对名调用 purge", async () => {
  api.list.mockResolvedValue([ARCHIVED])
  prompt.mockResolvedValue({ value: "Beta" })
  api.purge.mockResolvedValue({ deleted_nodes: 0, deleted_schemas: 0 })
  const w = await mountView()
  await w.findAll("button").find((b) => b.text() === "永久删除")!.trigger("click")
  await flushPromises()
  expect(api.purge).toHaveBeenCalledWith(2)
})
