import { it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"
import { roleAtLeast } from "@/types/graph"

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock("@/api/projects", () => ({ projectsApi: api }))

import { useProjectStore } from "@/stores/project"

beforeEach(() => {
  setActivePinia(createPinia())
  api.get.mockReset()
})

it("roleAtLeast 角色等级比较", () => {
  expect(roleAtLeast("admin", "editor")).toBe(true)
  expect(roleAtLeast("viewer", "admin")).toBe(false)
  expect(roleAtLeast("owner", "owner")).toBe(true)
  expect(roleAtLeast(null, "viewer")).toBe(false)
})

it("load 填 current 并驱动 can()", async () => {
  api.get.mockResolvedValue({ id: 1, name: "p", description: null, status: "active", created_by: 1, my_role: "admin" })
  const store = useProjectStore()
  await store.load(1)
  expect(store.current?.name).toBe("p")
  expect(store.can("editor")).toBe(true)
  expect(store.can("owner")).toBe(false)
})

it("无 current 时 can() 全 false", () => {
  const store = useProjectStore()
  expect(store.can("viewer")).toBe(false)
})

it("clear 清空 current", async () => {
  api.get.mockResolvedValue({ id: 1, name: "p", description: null, status: "active", created_by: 1, my_role: "owner" })
  const store = useProjectStore()
  await store.load(1)
  store.clear()
  expect(store.current).toBeNull()
})
