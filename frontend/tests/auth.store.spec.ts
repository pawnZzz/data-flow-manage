import { it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"

const api = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  getMe: vi.fn(),
  updateMe: vi.fn(),
  changePassword: vi.fn(),
}))
vi.mock("@/api/auth", () => ({ authApi: api }))

import { useAuthStore } from "@/stores/auth"

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  Object.values(api).forEach((f) => f.mockReset())
})

it("login 存 token 到 state+localStorage 并拉取 user", async () => {
  api.login.mockResolvedValue({ access_token: "tk", token_type: "bearer" })
  api.getMe.mockResolvedValue({ id: 1, username: "u", email: "u@x.com", display_name: null, status: "active" })
  const store = useAuthStore()
  await store.login("u", "p")
  expect(store.token).toBe("tk")
  expect(localStorage.getItem("token")).toBe("tk")
  expect(store.user?.username).toBe("u")
  expect(store.isAuthenticated).toBe(true)
})

it("register 不自动登录", async () => {
  api.register.mockResolvedValue({ id: 1, username: "u", email: "u@x.com", display_name: null, status: "active" })
  const store = useAuthStore()
  await store.register({ username: "u", email: "u@x.com", password: "secret" })
  expect(store.isAuthenticated).toBe(false)
  expect(api.login).not.toHaveBeenCalled()
})

it("logout 清空 token+user", async () => {
  api.logout.mockResolvedValue(undefined)
  const store = useAuthStore()
  store.setToken("tk")
  store.user = { id: 1, username: "u", email: "u@x.com", display_name: null, status: "active" }
  await store.logout()
  expect(store.token).toBeNull()
  expect(localStorage.getItem("token")).toBeNull()
  expect(store.user).toBeNull()
})

it("logout 即便接口失败也清本地", async () => {
  api.logout.mockRejectedValue(new Error("boom"))
  const store = useAuthStore()
  store.setToken("tk")
  await store.logout()
  expect(store.token).toBeNull()
})
