import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"

const load = vi.hoisted(() => vi.fn())
const store = { current: { id: 1, name: "Alpha", status: "active" }, load }
vi.mock("@/stores/project", () => ({ useProjectStore: () => store }))
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { pid: "1" } }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterView: { template: "<div class='rv' />" },
  RouterLink: { props: ["to"], template: "<a><slot/></a>" },
}))

import ProjectLayout from "@/views/ProjectLayout.vue"

beforeEach(() => { load.mockReset(); load.mockResolvedValue(undefined) })

it("挂载即 load 当前项目并渲染导航", async () => {
  const w = mount(ProjectLayout, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(load).toHaveBeenCalledWith(1)
  expect(w.text()).toContain("Alpha")
  expect(w.text()).toContain("成员")
  expect(w.text()).toContain("类型 Schema")
})
