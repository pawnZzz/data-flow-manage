import { it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"

let authed = false
vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ get isAuthenticated() { return authed } }),
}))

import router from "@/router"

beforeEach(() => {
  setActivePinia(createPinia())
  authed = false
})

it("未登录访问 /profile 重定向 /login", async () => {
  authed = false
  await router.push("/profile")
  await router.isReady()
  expect(router.currentRoute.value.name).toBe("login")
})

it("已登录访问 /login 重定向到 /", async () => {
  authed = true
  // 路由是单例，先离开 /login（上个用例可能停在此），确保下一次 push 是真实导航
  await router.push("/profile")
  await router.push("/login")
  await router.isReady()
  expect(router.currentRoute.value.path).toBe("/projects")
})
