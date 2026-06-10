import { it, expect, beforeEach, vi } from "vitest"
import { mount } from "@vue/test-utils"
import ElementPlus from "element-plus"

const warn = vi.hoisted(() => vi.fn())
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { warning: warn } }
})

import SchemaForm from "@/components/SchemaForm.vue"

// el-dialog teleports to body and renders its body lazily (one tick late),
// which the synchronous queries below cannot see. Stub it with a passthrough
// that renders the default + footer slots inline and synchronously.
const ElDialogStub = { template: '<div class="dlg"><slot /><slot name="footer" /></div>' }

beforeEach(() => warn.mockReset())

function mountForm(props = {}) {
  return mount(SchemaForm, {
    props: { visible: true, isEdit: false, schema: null, ...props },
    global: { plugins: [ElementPlus], stubs: { ElDialog: ElDialogStub } },
  })
}

it("添加/删除字段行", async () => {
  const w = mountForm()
  await w.findAll("button").find((b) => b.text() === "添加字段")!.trigger("click")
  expect(w.findAll(".field-row").length).toBe(1)
  await w.findAll("button").find((b) => b.text() === "删除")!.trigger("click")
  expect(w.findAll(".field-row").length).toBe(0)
})

it("enum 字段显示 options 输入，string 字段不显示", () => {
  const schema = {
    id: "s", type_key: "t", display_name: "T", created_at: "", updated_at: "",
    fields: [
      { name: "engine", label: "引擎", type: "enum", required: true, options: ["spark", "hive"] },
      { name: "sla", label: "SLA", type: "string", required: false, options: null },
    ],
  }
  const w = mountForm({ isEdit: true, schema })
  const rows = w.findAll(".field-row")
  expect(rows.length).toBe(2)
  const placeholders = w.findAll("input").map((i) => i.attributes("placeholder"))
  expect(placeholders).toContain("选项,逗号分隔")
})

it("缺 type_key 校验拦截（非编辑模式）", async () => {
  const w = mountForm({ isEdit: false })
  await w.findAll("button").find((b) => b.text() === "保存")!.trigger("click")
  expect(warn).toHaveBeenCalled()
})

it("提交规范化 payload：非 enum 的 options 为 null", async () => {
  const w = mountForm({ isEdit: true, schema: { id: "s", type_key: "t", display_name: "T", fields: [], created_at: "", updated_at: "" } })
  await w.findAll("button").find((b) => b.text() === "添加字段")!.trigger("click")
  const inputs = w.find(".field-row").findAll("input")
  await inputs[0].setValue("engine")
  await inputs[1].setValue("引擎")
  await w.findAll("button").find((b) => b.text() === "保存")!.trigger("click")
  const emitted = w.emitted("submit")
  expect(emitted).toBeTruthy()
  const payload = emitted![0][0] as { fields: { name: string; options: unknown }[] }
  expect(payload.fields[0].name).toBe("engine")
  expect(payload.fields[0].options).toBeNull()
})
