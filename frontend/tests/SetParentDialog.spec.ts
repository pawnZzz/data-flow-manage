import { it, expect } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"
import SetParentDialog from "@/components/graph/SetParentDialog.vue"

const CANDS = [{ id: "p1", name: "parent1" }, { id: "p2", name: "parent2" }]

const ElDialogStub = { template: '<div class="dlg"><slot /><slot name="footer" /></div>' }

function mountDlg(props = {}) {
  return mount(SetParentDialog, {
    props: { visible: true, candidates: CANDS, ...props },
    global: { plugins: [ElementPlus], stubs: { ElDialog: ElDialogStub } },
    attachTo: document.body,
  })
}

it("无选择时确定禁用", () => {
  const w = mountDlg()
  const ok = w.findAll("button").find((b) => b.text() === "确定")!
  expect(ok.attributes("disabled")).toBeDefined()
})

it("选父后提交 emit parentId", async () => {
  const w = mountDlg()
  ;(w.vm as unknown as { setParentId: (id: string) => void }).setParentId("p2")
  await flushPromises()
  await w.findAll("button").find((b) => b.text() === "确定")!.trigger("click")
  expect(w.emitted("submit")?.[0]).toEqual(["p2"])
})
