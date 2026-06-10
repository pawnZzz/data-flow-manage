import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import { setActivePinia, createPinia } from "pinia"
import ElementPlus from "element-plus"

const updateProfile = vi.fn()
const changePassword = vi.fn()
const logout = vi.fn()
const fetchMe = vi.fn()
const store = {
  user: { id: 1, username: "alice", email: "a@x.com", display_name: "A", status: "active" },
  updateProfile, changePassword, logout, fetchMe,
}
vi.mock("@/stores/auth", () => ({ useAuthStore: () => store }))
const push = vi.fn()
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }))

import ProfileView from "@/views/ProfileView.vue"

function mountView() {
  return mount(ProfileView, { global: { plugins: [ElementPlus] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  ;[updateProfile, changePassword, logout, fetchMe, push].forEach((f) => f.mockReset())
})

it("渲染用户信息", () => {
  const w = mountView()
  expect(w.text()).toContain("alice")
  expect(w.text()).toContain("a@x.com")
})

it("保存显示名调 updateProfile", async () => {
  updateProfile.mockResolvedValue(undefined)
  const w = mountView()
  await w.findAll("button").find((b) => b.text() === "保存")!.trigger("click")
  await flushPromises()
  expect(updateProfile).toHaveBeenCalledWith("A")
})

it("登出调 logout 并跳登录", async () => {
  logout.mockResolvedValue(undefined)
  const w = mountView()
  await w.findAll("button").find((b) => b.text() === "登出")!.trigger("click")
  await flushPromises()
  expect(logout).toHaveBeenCalled()
  expect(push).toHaveBeenCalledWith("/login")
})

it("填写有效密码后调 changePassword", async () => {
  changePassword.mockResolvedValue(undefined)
  const w = mountView()
  const inputs = w.findAll("input")
  // 顺序：显示名、原密码、新密码
  await inputs[1].setValue("oldpass")
  await inputs[2].setValue("newpass")
  await w.findAll("button").find((b) => b.text() === "修改密码")!.trigger("click")
  await flushPromises()
  expect(changePassword).toHaveBeenCalledWith("oldpass", "newpass")
})
