import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"

const api = vi.hoisted(() => ({ list: vi.fn(), add: vi.fn(), changeRole: vi.fn(), remove: vi.fn() }))
vi.mock("@/api/members", () => ({ membersApi: api }))
vi.mock("vue-router", () => ({ useRoute: () => ({ params: { pid: "1" } }) }))
const canState = vi.hoisted(() => ({ value: true }))
vi.mock("@/stores/project", () => ({ useProjectStore: () => ({ can: () => canState.value }) }))
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { success: vi.fn() }, ElMessageBox: { confirm: vi.fn().mockResolvedValue(true) } }
})

import MembersView from "@/views/MembersView.vue"

const MEMBERS = [
  { user_id: 1, username: "owner", display_name: null, role: "owner" },
  { user_id: 2, username: "bob", display_name: null, role: "viewer" },
]

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  canState.value = true
  api.list.mockResolvedValue(MEMBERS)
})

async function mountView() {
  const w = mount(MembersView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

it("渲染成员列表", async () => {
  const w = await mountView()
  expect(w.text()).toContain("owner")
  expect(w.text()).toContain("bob")
})

it("admin 可见添加成员按钮", async () => {
  canState.value = true
  const w = await mountView()
  expect(w.findAll("button").some((b) => b.text() === "添加成员")).toBe(true)
})

it("非 admin 不显示添加成员按钮", async () => {
  canState.value = false
  const w = await mountView()
  expect(w.findAll("button").some((b) => b.text() === "添加成员")).toBe(false)
})

it("移除非 owner 成员调 remove", async () => {
  api.remove.mockResolvedValue(undefined)
  const w = await mountView()
  await w.findAll("button").find((b) => b.text() === "移除")!.trigger("click")
  await flushPromises()
  expect(api.remove).toHaveBeenCalledWith(1, 2)
})
