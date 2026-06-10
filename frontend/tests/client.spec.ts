import { it, expect, beforeEach, vi, afterEach } from "vitest"

const messages: string[] = []
vi.mock("element-plus", () => ({
  ElMessage: { error: (m: string) => messages.push(m) },
}))

beforeEach(() => {
  localStorage.clear()
  messages.length = 0
  vi.resetModules()
})

afterEach(() => {
  vi.restoreAllMocks()
})

async function loadClient() {
  const mod = await import("@/api/client")
  return mod.http
}

it("请求拦截器在有 token 时加 Bearer 头", async () => {
  localStorage.setItem("token", "abc")
  const http = await loadClient()
  const handler = (http.interceptors.request as any).handlers[0].fulfilled
  const cfg = handler({ headers: {} })
  expect(cfg.headers.Authorization).toBe("Bearer abc")
})

it("无 token 时不加 Authorization 头", async () => {
  const http = await loadClient()
  const handler = (http.interceptors.request as any).handlers[0].fulfilled
  const cfg = handler({ headers: {} })
  expect(cfg.headers.Authorization).toBeUndefined()
})

it("非登录路径 401 清 token 并跳转 /login", async () => {
  localStorage.setItem("token", "abc")
  const assign = vi.fn()
  vi.stubGlobal("location", { assign } as any)
  const http = await loadClient()
  const onRejected = (http.interceptors.response as any).handlers[0].rejected
  const err = {
    config: { url: "/auth/me" },
    response: { status: 401, data: { error: { code: "AUTH_ERROR", message: "过期", details: {} } } },
  }
  await expect(onRejected(err)).rejects.toMatchObject({ status: 401, code: "AUTH_ERROR" })
  expect(localStorage.getItem("token")).toBeNull()
  expect(assign).toHaveBeenCalledWith("/login")
})

it("登录路径 401 不跳转不弹全局，仅归一化抛出", async () => {
  const assign = vi.fn()
  vi.stubGlobal("location", { assign } as any)
  const http = await loadClient()
  const onRejected = (http.interceptors.response as any).handlers[0].rejected
  const err = {
    config: { url: "/auth/login" },
    response: { status: 401, data: { error: { code: "AUTH_ERROR", message: "凭证错误", details: {} } } },
  }
  await expect(onRejected(err)).rejects.toMatchObject({ code: "AUTH_ERROR" })
  expect(assign).not.toHaveBeenCalled()
  expect(messages).toEqual([])
})

it("非静默路径其他错误弹全局消息", async () => {
  const http = await loadClient()
  const onRejected = (http.interceptors.response as any).handlers[0].rejected
  const err = {
    config: { url: "/nodes" },
    response: { status: 409, data: { error: { code: "CONFLICT", message: "冲突", details: {} } } },
  }
  await expect(onRejected(err)).rejects.toMatchObject({ status: 409 })
  expect(messages).toContain("冲突")
})
