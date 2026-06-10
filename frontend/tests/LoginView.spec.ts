import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import { setActivePinia, createPinia } from "pinia"
import ElementPlus from "element-plus"

const login = vi.fn()
const register = vi.fn()
vi.mock("@/stores/auth", () => ({ useAuthStore: () => ({ login, register }) }))
const push = vi.fn()
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }))

import LoginView from "@/views/LoginView.vue"

function mountView() {
  return mount(LoginView, { global: { plugins: [ElementPlus] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  login.mockReset(); register.mockReset(); push.mockReset()
})

it("渲染登录与注册 tab", () => {
  const w = mountView()
  expect(w.text()).toContain("登录")
  expect(w.text()).toContain("注册")
})

it("有效登录调 store.login 并跳转", async () => {
  login.mockResolvedValue(undefined)
  const w = mountView()
  await w.findAll("input")[0].setValue("alice")
  await w.findAll("input")[1].setValue("secret")
  await w.find("button").trigger("click")
  await flushPromises()
  expect(login).toHaveBeenCalledWith("alice", "secret")
  expect(push).toHaveBeenCalledWith("/")
})

it("登录失败(401)就地显示错误", async () => {
  login.mockRejectedValue({ status: 401, code: "AUTH_ERROR", message: "x", details: {} })
  const w = mountView()
  await w.findAll("input")[0].setValue("alice")
  await w.findAll("input")[1].setValue("bad")
  await w.find("button").trigger("click")
  await flushPromises()
  expect(w.text()).toContain("用户名或密码错误")
  expect(push).not.toHaveBeenCalled()
})
