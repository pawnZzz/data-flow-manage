import { it, expect } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"
import CreateNodeDialog from "@/components/graph/CreateNodeDialog.vue"

const SCHEMAS = [{ id: "s1", type_key: "data_task", display_name: "数据任务", fields: [], created_at: "", updated_at: "" }]

const ElDialogStub = { template: '<div class="dlg"><slot /><slot name="footer" /></div>' }

function mountDlg(props = {}) {
  return mount(CreateNodeDialog, {
    props: { visible: true, schemas: SCHEMAS, ...props },
    global: { plugins: [ElementPlus], stubs: { ElDialog: ElDialogStub } },
    attachTo: document.body,
  })
}

it("空 schemas 显示提示且禁用创建", () => {
  const w = mountDlg({ schemas: [] })
  expect(w.text()).toContain("请先在 Schema 管理中创建类型")
  const create = w.findAll("button").find((b) => b.text() === "创建")!
  expect(create.attributes("disabled")).toBeDefined()
})

it("缺 name/type 校验拦截提交", async () => {
  const w = mountDlg()
  await w.findAll("button").find((b) => b.text() === "创建")!.trigger("click")
  await flushPromises()
  expect(w.emitted("submit")).toBeFalsy()
})

it("填全后提交 emit {name,type}", async () => {
  const w = mountDlg()
  await w.find("input").setValue("ods")
  ;(w.vm as unknown as { form: { type: string } }).form.type = "data_task"
  await flushPromises()
  await w.findAll("button").find((b) => b.text() === "创建")!.trigger("click")
  await flushPromises()
  expect(w.emitted("submit")?.[0]).toEqual([{ name: "ods", type: "data_task" }])
})
