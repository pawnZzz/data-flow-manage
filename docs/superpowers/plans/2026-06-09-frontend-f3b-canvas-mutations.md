# 前端 F3b：X6 画布变更 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 F3a 只读画布可编辑：工具条建节点、X6 拖连建边（成环预警/冲突撤销）、右键菜单删/设父（下拉）/解父、删边，全部变更后重拉同步，editor+ 显隐。

**Architecture:** 变更逻辑放 graphStore actions（调 api → 成功后 loadGraph 重拉，记 currentPid）；graphController 加编辑方法（connecting/contextmenu/removeEdgeCell）；GraphCanvas editable prop + 新 emits（临时边在 canvas 内移除）；GraphView 接线菜单/对话框/store。复用 F3a 全部既有件。

**Tech Stack:** Vue 3(`<script setup>`+TS)、Pinia、Element Plus、@antv/x6@3、Vitest、@vue/test-utils。

参考 spec：`docs/superpowers/specs/2026-06-09-frontend-f3b-canvas-mutations-design.md`。

---

## File Structure

- `frontend/src/api/edges.ts` — 新建：createEdge/deleteEdge。
- `frontend/src/api/nodes.ts` — 改：加 create/remove/setParent/clearParent（保留 list）。
- `frontend/src/stores/graph.ts` — 改：currentPid + 6 个 mutation actions。
- `frontend/src/components/graph/graphController.ts` — 改：setEditable/enableConnecting/onEdgeConnected/removeEdgeCell/onNodeContextmenu/onEdgeContextmenu。
- `frontend/src/components/graph/GraphCanvas.vue` — 改：editable prop + 新 emits + 临时边移除。
- `frontend/src/components/graph/CreateNodeDialog.vue`、`SetParentDialog.vue`、`NodeContextMenu.vue` — 新建。
- `frontend/src/views/GraphView.vue` — 改：工具条新建、菜单/对话框接线、编辑事件→store。
- 测试：graph.store.mutations、CreateNodeDialog、SetParentDialog、NodeContextMenu、GraphCanvas(改)、GraphView.mutations。

约定：命令在 `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend` 下跑；commit 在仓库根；message 末尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。`@`→src。

## Task 1: api edges/nodes + store mutation actions

**Files:**
- Create: `frontend/src/api/edges.ts`
- Modify: `frontend/src/api/nodes.ts`, `frontend/src/stores/graph.ts`
- Test: `frontend/tests/graph.store.mutations.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/api/edges.ts`**

```ts
import { http } from "./client"
import type { GraphEdge } from "@/types/graph"

export interface CreateEdgeResponse {
  edge: GraphEdge
  warnings: { creates_cycle: boolean }
}

export const edgesApi = {
  create: (pid: number, body: { source_id: string; target_id: string; edge_type?: string }) =>
    http.post(`/projects/${pid}/edges`, body) as unknown as Promise<CreateEdgeResponse>,
  remove: (pid: number, eid: string) =>
    http.delete(`/projects/${pid}/edges/${eid}`) as unknown as Promise<void>,
}
```

- [ ] **Step 2: 改 `frontend/src/api/nodes.ts`（加方法，保留 list）**

整个文件替换为：
```ts
import { http } from "./client"
import type { NodeFilters, NodeResponse } from "@/types/graph"

export const nodesApi = {
  list: (pid: number, filters: NodeFilters = {}) =>
    http.get(`/projects/${pid}/nodes`, { params: filters }) as unknown as Promise<NodeResponse[]>,
  create: (pid: number, body: { name: string; type: string }) =>
    http.post(`/projects/${pid}/nodes`, body) as unknown as Promise<NodeResponse>,
  remove: (pid: number, nid: string) =>
    http.delete(`/projects/${pid}/nodes/${nid}`) as unknown as Promise<void>,
  setParent: (pid: number, nid: string, parent_id: string) =>
    http.post(`/projects/${pid}/nodes/${nid}/parent`, { parent_id }) as unknown as Promise<void>,
  clearParent: (pid: number, nid: string) =>
    http.delete(`/projects/${pid}/nodes/${nid}/parent`) as unknown as Promise<void>,
}
```

- [ ] **Step 3: 改 `frontend/src/stores/graph.ts`**

顶部 import 加 `import { edgesApi } from "@/api/edges"`（`nodesApi` 已有）。

在 state 区加 `const currentPid = ref<number | null>(null)`。

`loadGraph` 函数体首行加 `currentPid.value = pid`（在 await 之前）：
```ts
  async function loadGraph(pid: number) {
    currentPid.value = pid
    const [sg, nodes] = await Promise.all([graphApi.getSubgraph(pid), nodesApi.list(pid)])
    subgraph.value = sg
    sidebarNodes.value = nodes
  }
```

在 `clear` 之前加 mutation actions：
```ts
  function pid(): number {
    if (currentPid.value === null) throw new Error("no current project loaded")
    return currentPid.value
  }

  async function createNode(body: { name: string; type: string }) {
    const node = await nodesApi.create(pid(), body)
    await loadGraph(pid())
    return node
  }
  async function deleteNode(nid: string) {
    await nodesApi.remove(pid(), nid)
    await loadGraph(pid())
  }
  async function createEdge(body: { source_id: string; target_id: string; edge_type?: string }) {
    const res = await edgesApi.create(pid(), body)
    await loadGraph(pid())
    return res
  }
  async function deleteEdge(eid: string) {
    await edgesApi.remove(pid(), eid)
    await loadGraph(pid())
  }
  async function setParent(nid: string, parentId: string) {
    await nodesApi.setParent(pid(), nid, parentId)
    await loadGraph(pid())
  }
  async function clearParent(nid: string) {
    await nodesApi.clearParent(pid(), nid)
    await loadGraph(pid())
  }
```
在 `clear()` 里加 `currentPid.value = null`。把这些加进 return 对象：`currentPid, createNode, deleteNode, createEdge, deleteEdge, setParent, clearParent`（连同已有的）。

- [ ] **Step 4: 写测试 `frontend/tests/graph.store.mutations.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"

const graphApi = vi.hoisted(() => ({ getSubgraph: vi.fn() }))
const nodesApi = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), remove: vi.fn(), setParent: vi.fn(), clearParent: vi.fn() }))
const edgesApi = vi.hoisted(() => ({ create: vi.fn(), remove: vi.fn() }))
vi.mock("@/api/graph", () => ({ graphApi }))
vi.mock("@/api/nodes", () => ({ nodesApi }))
vi.mock("@/api/edges", () => ({ edgesApi }))

import { useGraphStore } from "@/stores/graph"

const SG = { nodes: [], edges: [], stats: { node_count: 0, edge_count: 0, has_cycle: false } }

beforeEach(() => {
  setActivePinia(createPinia())
  ;[graphApi.getSubgraph, nodesApi.list, nodesApi.create, nodesApi.remove, nodesApi.setParent, nodesApi.clearParent, edgesApi.create, edgesApi.remove].forEach((f) => f.mockReset())
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue([])
})

async function loaded() {
  const s = useGraphStore()
  await s.loadGraph(7)
  graphApi.getSubgraph.mockClear()
  nodesApi.list.mockClear()
  return s
}

it("createNode 调 api 并重拉", async () => {
  const s = await loaded()
  nodesApi.create.mockResolvedValue({ id: "n" })
  await s.createNode({ name: "x", type: "t" })
  expect(nodesApi.create).toHaveBeenCalledWith(7, { name: "x", type: "t" })
  expect(graphApi.getSubgraph).toHaveBeenCalledWith(7)
})

it("createEdge 调 api、重拉并透传 warnings", async () => {
  const s = await loaded()
  edgesApi.create.mockResolvedValue({ edge: { id: "e" }, warnings: { creates_cycle: true } })
  const res = await s.createEdge({ source_id: "a", target_id: "b" })
  expect(edgesApi.create).toHaveBeenCalledWith(7, { source_id: "a", target_id: "b" })
  expect(res.warnings.creates_cycle).toBe(true)
  expect(graphApi.getSubgraph).toHaveBeenCalledWith(7)
})

it("deleteNode/deleteEdge/setParent/clearParent 调 api 并重拉", async () => {
  const s = await loaded()
  nodesApi.remove.mockResolvedValue(undefined)
  edgesApi.remove.mockResolvedValue(undefined)
  nodesApi.setParent.mockResolvedValue(undefined)
  nodesApi.clearParent.mockResolvedValue(undefined)
  await s.deleteNode("n")
  await s.deleteEdge("e")
  await s.setParent("c", "p")
  await s.clearParent("c")
  expect(nodesApi.remove).toHaveBeenCalledWith(7, "n")
  expect(edgesApi.remove).toHaveBeenCalledWith(7, "e")
  expect(nodesApi.setParent).toHaveBeenCalledWith(7, "c", "p")
  expect(nodesApi.clearParent).toHaveBeenCalledWith(7, "c")
  expect(graphApi.getSubgraph).toHaveBeenCalledTimes(4)
})

it("api 抛错时不重拉、错误冒泡", async () => {
  const s = await loaded()
  nodesApi.create.mockRejectedValue(new Error("409"))
  await expect(s.createNode({ name: "x", type: "t" })).rejects.toThrow()
  expect(graphApi.getSubgraph).not.toHaveBeenCalled()
})
```

- [ ] **Step 5: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -8`
Expected: 全绿（既有 69 + 本任务 4 = 73）。

- [ ] **Step 6: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/api/edges.ts frontend/src/api/nodes.ts frontend/src/stores/graph.ts frontend/tests/graph.store.mutations.spec.ts
git commit -m "feat(frontend): F3b 边/节点写 API 与 graph store 变更 actions（重拉同步）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

Do NOT run `npm run build`（GraphView 编辑接线在后续任务）。

## Task 2: graphController 编辑方法 + GraphCanvas editable

**Files:**
- Modify: `frontend/src/components/graph/graphController.ts`, `frontend/src/components/graph/GraphCanvas.vue`
- Modify (test): `frontend/tests/GraphCanvas.spec.ts`（既有 mock 加新方法 + 新用例）

- [ ] **Step 1: 在 `graphController.ts` 加编辑方法**

在 `dispose()` 之前追加（类内）：
```ts
  setEditable(on: boolean): void {
    if (!this.graph) return
    this.graph.options.connecting = on
      ? { allowBlank: false, allowLoop: false, allowMulti: false, router: "normal" }
      : { allowBlank: false, allowLoop: false, allowMulti: false }
    // nodeMovable 始终允许（只读也可拖看）；connecting 由可交互性控制
  }

  onEdgeConnected(cb: (sourceId: string, targetId: string, edgeId: string) => void): void {
    this.graph?.on("edge:connected", ({ edge }) => {
      const s = edge.getSourceCellId()
      const t = edge.getTargetCellId()
      if (s && t) cb(s, t, edge.id)
    })
  }

  removeEdgeCell(edgeId: string): void {
    const cell = this.graph?.getCellById(edgeId)
    if (cell?.isEdge()) cell.remove()
  }

  onNodeContextmenu(cb: (id: string, x: number, y: number) => void): void {
    this.graph?.on("node:contextmenu", ({ node, e }) => cb(node.id, e.clientX, e.clientY))
  }

  onEdgeContextmenu(cb: (id: string, x: number, y: number) => void): void {
    this.graph?.on("edge:contextmenu", ({ edge, e }) => cb(edge.id, e.clientX, e.clientY))
  }
```
> VERIFY X6 v3 API: `graph.options.connecting` mutability, `edge.getSourceCellId()/getTargetCellId()`, `cell.isEdge()`, `cell.remove()`, `node:contextmenu`/`edge:contextmenu` event payload `{node/edge, e}` with `e.clientX/clientY`. Adjust to real v3 signatures, keeping the contract method names. If `connecting` must be set at init (not mutable post-init), instead store an `editable` flag and gate via `graph.options.interacting` / a `validateConnection` that returns the flag. Report what you used.

- [ ] **Step 2: 改 `GraphCanvas.vue`**

`defineProps` 加 `editable: boolean`。`defineEmits` 加：
```ts
const emit = defineEmits<{
  select: [id: string]
  nodeMoved: [id: string, xy: XYPos]
  edgeConnected: [sourceId: string, targetId: string, edgeId: string]
  nodeContextmenu: [id: string, x: number, y: number]
  edgeContextmenu: [id: string, x: number, y: number]
}>()
```
onMounted 内（在 init 之后、render 之前）加：
```ts
  controller.setEditable(props.editable)
  controller.onEdgeConnected((s, t, edgeId) => {
    controller.removeEdgeCell(edgeId)   // 临时边移除，画面以重拉为准
    emit("edgeConnected", s, t, edgeId)
  })
  controller.onNodeContextmenu((id, x, y) => emit("nodeContextmenu", id, x, y))
  controller.onEdgeContextmenu((id, x, y) => emit("edgeContextmenu", id, x, y))
```
加 watch：`watch(() => props.editable, (on) => controller.setEditable(on))`。

- [ ] **Step 3: 改 `frontend/tests/GraphCanvas.spec.ts`**

把 `calls` 的 `vi.hoisted` 对象加上新方法：
```ts
const calls = vi.hoisted(() => ({
  init: vi.fn(), setData: vi.fn(), applyPositions: vi.fn(), runLayout: vi.fn().mockResolvedValue({}),
  highlightSelected: vi.fn(), applyMatch: vi.fn(), centerOn: vi.fn(),
  onNodeClick: vi.fn(), onNodeMoved: vi.fn(), dispose: vi.fn(),
  setEditable: vi.fn(), onEdgeConnected: vi.fn(), removeEdgeCell: vi.fn(),
  onNodeContextmenu: vi.fn(), onEdgeContextmenu: vi.fn(),
}))
```
`mountCanvas` 默认 props 加 `editable: false`（既有用例不受影响）。在文件末尾加新用例：
```ts
it("editable=true 时 setEditable(true) 并注册编辑回调", async () => {
  mountCanvas({ editable: true })
  await flushPromises()
  expect(calls.setEditable).toHaveBeenCalledWith(true)
  expect(calls.onEdgeConnected).toHaveBeenCalled()
  expect(calls.onNodeContextmenu).toHaveBeenCalled()
  expect(calls.onEdgeContextmenu).toHaveBeenCalled()
})

it("editable=false 时 setEditable(false)", async () => {
  mountCanvas({ editable: false })
  await flushPromises()
  expect(calls.setEditable).toHaveBeenCalledWith(false)
})

it("edge:connected 回调先 removeEdgeCell 再 emit edgeConnected", async () => {
  const w = mountCanvas({ editable: true })
  await flushPromises()
  const cb = calls.onEdgeConnected.mock.calls[0][0] as (s: string, t: string, id: string) => void
  cb("a", "b", "tmpEdge")
  expect(calls.removeEdgeCell).toHaveBeenCalledWith("tmpEdge")
  expect(w.emitted("edgeConnected")?.[0]).toEqual(["a", "b", "tmpEdge"])
})
```
> 既有 5 个用例保持（mountCanvas 默认 editable:false 时仍 init/setData/runLayout/dispose 不变；只是多调一次 setEditable(false)，不影响断言）。

- [ ] **Step 4: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -8`
Expected: 全绿（73 + GraphCanvas 新增 3 = 76；既有 GraphCanvas 5 仍过）。

- [ ] **Step 5: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/components/graph/graphController.ts frontend/src/components/graph/GraphCanvas.vue frontend/tests/GraphCanvas.spec.ts
git commit -m "feat(frontend): F3b graphController 编辑方法与 GraphCanvas editable

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 3: CreateNodeDialog + SetParentDialog + NodeContextMenu

**Files:**
- Create: `frontend/src/components/graph/CreateNodeDialog.vue`, `frontend/src/components/graph/SetParentDialog.vue`, `frontend/src/components/graph/NodeContextMenu.vue`
- Test: `frontend/tests/CreateNodeDialog.spec.ts`, `frontend/tests/SetParentDialog.spec.ts`, `frontend/tests/NodeContextMenu.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/components/graph/CreateNodeDialog.vue`**

```vue
<template>
  <el-dialog :model-value="visible" title="新建节点" @update:model-value="emit('close')">
    <el-alert v-if="schemas.length === 0" type="warning" :closable="false" title="请先在 Schema 管理中创建类型" />
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent>
      <el-form-item prop="name" label="名称">
        <el-input v-model="form.name" placeholder="节点名称" />
      </el-form-item>
      <el-form-item prop="type" label="类型">
        <el-select v-model="form.type" placeholder="选择类型">
          <el-option v-for="s in schemas" :key="s.type_key" :label="s.display_name" :value="s.type_key" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :disabled="schemas.length === 0" @click="onSubmit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from "vue"
import { type FormInstance, type FormRules } from "element-plus"
import type { NodeTypeSchema } from "@/types/graph"

const props = defineProps<{ visible: boolean; schemas: NodeTypeSchema[] }>()
const emit = defineEmits<{ close: []; submit: [{ name: string; type: string }] }>()

const formRef = ref<FormInstance>()
const form = reactive({ name: "", type: "" })
const rules: FormRules = {
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  type: [{ required: true, message: "请选择类型", trigger: "change" }],
}

watch(() => props.visible, (v) => { if (v) { form.name = ""; form.type = "" } })

async function onSubmit() {
  if (!(await formRef.value?.validate().catch(() => false))) return
  emit("submit", { name: form.name, type: form.type })
}
</script>
```

- [ ] **Step 2: 创建 `frontend/src/components/graph/SetParentDialog.vue`**

```vue
<template>
  <el-dialog :model-value="visible" title="设置父节点" @update:model-value="emit('close')">
    <el-select v-model="parentId" placeholder="选择父节点" filterable style="width: 100%">
      <el-option v-for="c in candidates" :key="c.id" :label="c.name" :value="c.id" />
    </el-select>
    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :disabled="!parentId" @click="onSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"

const props = defineProps<{ visible: boolean; candidates: { id: string; name: string }[] }>()
const emit = defineEmits<{ close: []; submit: [parentId: string] }>()

const parentId = ref("")
watch(() => props.visible, (v) => { if (v) parentId.value = "" })

function onSubmit() {
  if (parentId.value) emit("submit", parentId.value)
}
</script>
```

- [ ] **Step 3: 创建 `frontend/src/components/graph/NodeContextMenu.vue`**

```vue
<template>
  <ul v-if="visible" class="ctx-menu" :style="{ left: x + 'px', top: y + 'px' }" @click.stop>
    <template v-if="kind === 'node'">
      <li @click="emit('setParent')">设父节点</li>
      <li @click="emit('clearParent')">解除父</li>
      <li class="danger" @click="emit('delete')">删除节点</li>
    </template>
    <template v-else>
      <li class="danger" @click="emit('delete')">删除边</li>
    </template>
  </ul>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue"

const props = defineProps<{ visible: boolean; x: number; y: number; kind: "node" | "edge" }>()
const emit = defineEmits<{ delete: []; setParent: []; clearParent: []; close: [] }>()

function onDocClick() {
  if (props.visible) emit("close")
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape" && props.visible) emit("close")
}
onMounted(() => {
  document.addEventListener("click", onDocClick)
  document.addEventListener("keydown", onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick)
  document.removeEventListener("keydown", onKey)
})
</script>

<style scoped>
.ctx-menu { position: fixed; z-index: 3000; background: #fff; border: 1px solid #e4e7ed; border-radius: 4px; box-shadow: 0 2px 12px rgba(0,0,0,.1); padding: 4px 0; min-width: 120px; list-style: none; margin: 0; }
.ctx-menu li { padding: 6px 16px; cursor: pointer; font-size: 14px; }
.ctx-menu li:hover { background: #f5f7fa; }
.ctx-menu li.danger { color: #f56c6c; }
</style>
```

- [ ] **Step 4: 写测试 `frontend/tests/CreateNodeDialog.spec.ts`**

```ts
import { it, expect, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"
import CreateNodeDialog from "@/components/graph/CreateNodeDialog.vue"

const SCHEMAS = [{ id: "s1", type_key: "data_task", display_name: "数据任务", fields: [], created_at: "", updated_at: "" }]

function mountDlg(props = {}) {
  return mount(CreateNodeDialog, {
    props: { visible: true, schemas: SCHEMAS, ...props },
    global: { plugins: [ElementPlus] }, attachTo: document.body,
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
  // 直接设组件内 form.type（el-select 弹层交互繁琐）：通过 vm
  ;(w.vm as unknown as { form: { type: string } }).form.type = "data_task"
  await w.findAll("button").find((b) => b.text() === "创建")!.trigger("click")
  await flushPromises()
  expect(w.emitted("submit")?.[0]).toEqual([{ name: "ods", type: "data_task" }])
})
```
> 若 `w.vm.form` 因 `<script setup>` 不可直接访问，改用暴露或在 el-select 上 `setValue`；保持"填全后 emit {name,type}"断言。

- [ ] **Step 5: 写测试 `frontend/tests/SetParentDialog.spec.ts`**

```ts
import { it, expect } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"
import SetParentDialog from "@/components/graph/SetParentDialog.vue"

const CANDS = [{ id: "p1", name: "parent1" }, { id: "p2", name: "parent2" }]

function mountDlg(props = {}) {
  return mount(SetParentDialog, {
    props: { visible: true, candidates: CANDS, ...props },
    global: { plugins: [ElementPlus] }, attachTo: document.body,
  })
}

it("无选择时确定禁用", () => {
  const w = mountDlg()
  const ok = w.findAll("button").find((b) => b.text() === "确定")!
  expect(ok.attributes("disabled")).toBeDefined()
})

it("选父后提交 emit parentId", async () => {
  const w = mountDlg()
  ;(w.vm as unknown as { parentId: string }).parentId = "p2"
  await flushPromises()
  await w.findAll("button").find((b) => b.text() === "确定")!.trigger("click")
  expect(w.emitted("submit")?.[0]).toEqual(["p2"])
})
```
> 同理，若 vm.parentId 不可达改用 el-select setValue；保持"选后 emit parentId"。

- [ ] **Step 6: 写测试 `frontend/tests/NodeContextMenu.spec.ts`**

```ts
import { it, expect } from "vitest"
import { mount } from "@vue/test-utils"
import NodeContextMenu from "@/components/graph/NodeContextMenu.vue"

function mountMenu(props = {}) {
  return mount(NodeContextMenu, { props: { visible: true, x: 10, y: 20, kind: "node", ...props } })
}

it("node kind 显示删除/设父/解父", () => {
  const w = mountMenu({ kind: "node" })
  const txt = w.text()
  expect(txt).toContain("删除节点")
  expect(txt).toContain("设父节点")
  expect(txt).toContain("解除父")
})

it("edge kind 只显示删除边", () => {
  const w = mountMenu({ kind: "edge" })
  expect(w.text()).toContain("删除边")
  expect(w.text()).not.toContain("设父节点")
})

it("visible=false 不渲染", () => {
  const w = mountMenu({ visible: false })
  expect(w.find(".ctx-menu").exists()).toBe(false)
})

it("点删除 emit delete", async () => {
  const w = mountMenu({ kind: "node" })
  await w.findAll("li").find((li) => li.text() === "删除节点")!.trigger("click")
  expect(w.emitted("delete")).toBeTruthy()
})

it("点设父 emit setParent", async () => {
  const w = mountMenu({ kind: "node" })
  await w.findAll("li").find((li) => li.text() === "设父节点")!.trigger("click")
  expect(w.emitted("setParent")).toBeTruthy()
})
```

- [ ] **Step 7: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -10`
Expected: 全绿（76 + 本任务 ~10）。若 `w.vm.form`/`parentId` 在 `<script setup>` 下不可直接访问，按注释改用 el-select 交互或 expose，保持断言。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/components/graph/CreateNodeDialog.vue frontend/src/components/graph/SetParentDialog.vue frontend/src/components/graph/NodeContextMenu.vue frontend/tests/CreateNodeDialog.spec.ts frontend/tests/SetParentDialog.spec.ts frontend/tests/NodeContextMenu.spec.ts
git commit -m "feat(frontend): F3b 建节点/设父对话框与右键菜单组件

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 4: GraphView 编辑接线 + 构建

**Files:**
- Modify: `frontend/src/views/GraphView.vue`
- Test: `frontend/tests/GraphView.mutations.spec.ts`

- [ ] **Step 1: 改 `frontend/src/views/GraphView.vue`**

模板：工具条加新建按钮（在"重新布局"旁），传 editable 给 GraphCanvas，挂三个编辑事件，并加菜单/对话框。在 `<section class="canvas-area">` 的 toolbar 内、`重新布局` 之前加：
```html
        <el-button v-if="proj.can('editor')" size="small" type="primary" @click="openCreateNode">新建节点</el-button>
```
GraphCanvas 标签加属性/事件：
```html
      <GraphCanvas
        v-else
        ref="canvas"
        :subgraph="store.subgraph"
        :matched-ids="store.matchedIds"
        :selected-id="store.selectedId"
        :saved-positions="savedPositions"
        :editable="proj.can('editor')"
        @select="onSelect"
        @node-moved="onNodeMoved"
        @edge-connected="onEdgeConnected"
        @node-contextmenu="(id, x, y) => openMenu('node', id, x, y)"
        @edge-contextmenu="(id, x, y) => openMenu('edge', id, x, y)"
      />
```
在 `</section>` 后（`</div>` 前）加菜单与对话框：
```html
    <NodeContextMenu
      :visible="menu.visible" :x="menu.x" :y="menu.y" :kind="menu.kind"
      @delete="onMenuDelete" @set-parent="onMenuSetParent" @clear-parent="onMenuClearParent" @close="menu.visible = false"
    />
    <CreateNodeDialog :visible="createVisible" :schemas="schemas" @close="createVisible = false" @submit="onCreateNode" />
    <SetParentDialog :visible="parentVisible" :candidates="parentCandidates" @close="parentVisible = false" @submit="onSetParent" />
```
脚本加（在既有 onSelect/onNodeMoved/onRelayout 旁）：
```ts
import { ElMessage, ElMessageBox } from "element-plus"
import { useProjectStore } from "@/stores/project"
import { schemasApi } from "@/api/schemas"
import type { NodeTypeSchema } from "@/types/graph"
import CreateNodeDialog from "@/components/graph/CreateNodeDialog.vue"
import SetParentDialog from "@/components/graph/SetParentDialog.vue"
import NodeContextMenu from "@/components/graph/NodeContextMenu.vue"

const proj = useProjectStore()
const schemas = ref<NodeTypeSchema[]>([])
const createVisible = ref(false)
const parentVisible = ref(false)
const menu = reactive({ visible: false, kind: "node" as "node" | "edge", id: "", x: 0, y: 0 })
const parentTargetId = ref("")

const parentCandidates = computed(() =>
  store.sidebarNodes.filter((n) => n.id !== parentTargetId.value).map((n) => ({ id: n.id, name: n.name })),
)

async function openCreateNode() {
  schemas.value = await schemasApi.list(pid.value)
  createVisible.value = true
}
async function onCreateNode(body: { name: string; type: string }) {
  await store.createNode(body)
  createVisible.value = false
  ElMessage.success("节点已创建")
}
async function onEdgeConnected(sourceId: string, targetId: string) {
  const res = await store.createEdge({ source_id: sourceId, target_id: targetId })
  if (res.warnings.creates_cycle) ElMessage.warning("依赖已创建，但会形成环")
}
function openMenu(kind: "node" | "edge", id: string, x: number, y: number) {
  Object.assign(menu, { visible: true, kind, id, x, y })
}
async function onMenuDelete() {
  const { id, kind } = menu
  menu.visible = false
  await ElMessageBox.confirm(kind === "node" ? "删除该节点及其关系？" : "删除该依赖边？", "确认", { type: "warning" })
  if (kind === "node") await store.deleteNode(id)
  else await store.deleteEdge(id)
  ElMessage.success("已删除")
}
function onMenuSetParent() {
  parentTargetId.value = menu.id
  menu.visible = false
  parentVisible.value = true
}
async function onSetParent(parentId: string) {
  await store.setParent(parentTargetId.value, parentId)
  parentVisible.value = false
  ElMessage.success("父节点已设置")
}
async function onMenuClearParent() {
  const id = menu.id
  menu.visible = false
  await store.clearParent(id)
  ElMessage.success("已解除父节点")
}
```
（确保 `reactive`、`computed` 已 import；`pid`/`store`/`canvas`/`onSelect` 等 F3a 既有保留。）

- [ ] **Step 2: 写测试 `frontend/tests/GraphView.mutations.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"

const store = vi.hoisted(() => ({
  subgraph: { nodes: [{ id: "a", name: "a", type: "t", priority: null, is_critical: false, parent_id: null }], edges: [], stats: { node_count: 1, edge_count: 0, has_cycle: false } },
  sidebarNodes: [{ id: "a", name: "a" }, { id: "b", name: "b" }], selectedId: null, filters: {}, matchedIds: null,
  loadGraph: vi.fn().mockResolvedValue(undefined), select: vi.fn(), setFilter: vi.fn(), clearFilters: vi.fn(),
  createNode: vi.fn().mockResolvedValue({}), deleteNode: vi.fn().mockResolvedValue(undefined),
  createEdge: vi.fn().mockResolvedValue({ edge: {}, warnings: { creates_cycle: false } }),
  deleteEdge: vi.fn().mockResolvedValue(undefined), setParent: vi.fn().mockResolvedValue(undefined), clearParent: vi.fn().mockResolvedValue(undefined),
}))
const canEditor = vi.hoisted(() => ({ value: true }))
vi.mock("@/stores/graph", () => ({ useGraphStore: () => store }))
vi.mock("@/stores/project", () => ({ useProjectStore: () => ({ can: () => canEditor.value }) }))
vi.mock("@/stores/auth", () => ({ useAuthStore: () => ({ user: { id: 7 } }) }))
vi.mock("vue-router", () => ({ useRoute: () => ({ params: { pid: "1" } }) }))
vi.mock("@/api/schemas", () => ({ schemasApi: { list: vi.fn().mockResolvedValue([]) } }))
vi.mock("@/components/graph/GraphCanvas.vue", () => ({ default: { name: "GraphCanvas", template: "<div class='gc' />" } }))
vi.mock("@/components/sidebar/FilterBar.vue", () => ({ default: { name: "FilterBar", template: "<div />" } }))
vi.mock("@/components/sidebar/NodeTree.vue", () => ({ default: { name: "NodeTree", template: "<div />" } }))
vi.mock("@/components/graph/CreateNodeDialog.vue", () => ({ default: { name: "CreateNodeDialog", template: "<div />" } }))
vi.mock("@/components/graph/SetParentDialog.vue", () => ({ default: { name: "SetParentDialog", template: "<div />" } }))
vi.mock("@/components/graph/NodeContextMenu.vue", () => ({ default: { name: "NodeContextMenu", template: "<div />" } }))
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { success: vi.fn(), warning: vi.fn() }, ElMessageBox: { confirm: vi.fn().mockResolvedValue(true) } }
})

import ElementPlus from "element-plus"
import GraphView from "@/views/GraphView.vue"

function mountView() {
  return mount(GraphView, { global: { plugins: [ElementPlus] } })
}

beforeEach(() => { canEditor.value = true; Object.values(store).forEach((f) => (f as any).mockClear?.()) })

it("editor 显示新建节点按钮", async () => {
  const w = mountView(); await flushPromises()
  expect(w.findAll("button").some((b) => b.text() === "新建节点")).toBe(true)
})

it("viewer 不显示新建节点", async () => {
  canEditor.value = false
  const w = mountView(); await flushPromises()
  expect(w.findAll("button").some((b) => b.text() === "新建节点")).toBe(false)
})

it("edgeConnected 调 store.createEdge", async () => {
  const w = mountView(); await flushPromises()
  w.findComponent({ name: "GraphCanvas" }).vm.$emit("edgeConnected", "a", "b", "tmp")
  await flushPromises()
  expect(store.createEdge).toHaveBeenCalledWith({ source_id: "a", target_id: "b" })
})

it("nodeContextmenu→删除 走 confirm 调 store.deleteNode", async () => {
  const w = mountView(); await flushPromises()
  w.findComponent({ name: "GraphCanvas" }).vm.$emit("nodeContextmenu", "a", 5, 6)
  await flushPromises()
  w.findComponent({ name: "NodeContextMenu" }).vm.$emit("delete")
  await flushPromises()
  expect(store.deleteNode).toHaveBeenCalledWith("a")
})
```

- [ ] **Step 3: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -10`
Expected: 全绿（前三任务 + GraphView.mutations 4）。若 `vm.$emit` 触发子组件事件的方式与 stub 不符，调整为在 stub 上声明 emits 或用 `wrapper.findComponent(...).vm.$emit`，保持"edgeConnected→createEdge""删除→deleteNode"断言。

- [ ] **Step 4: 类型检查 + 构建（F3b DoD 闸门）**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run build 2>&1 | tail -12`
Expected: vue-tsc 无类型错误，vite build 产出 dist/。按报错精确修，不放宽 strict。

- [ ] **Step 5: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/views/GraphView.vue frontend/tests/GraphView.mutations.spec.ts
git commit -m "feat(frontend): F3b GraphView 编辑接线（新建/连线/右键删·设父·解父）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Phase F3b 完成标准（Definition of Done）

- [ ] `npm run build`（vue-tsc）通过、无 TS 错误。
- [ ] `npm run test` 全绿（F1+F2+F3a 既有 69 + F3b 新增）。
- [ ] 手动（editor）：工具条新建节点（选 type）→ 出现；节点间拖连建边（成环弹 warning；重复/自环被拒、临时边撤销）；右键节点删除/设父（下拉）/解父；右键边删除；每次变更后画布重拉、已有节点位置保留。
- [ ] viewer：无编辑入口（无新建按钮、不能拖连、右键无编辑项），退回 F3a 只读。
- [ ] 归档项目：编辑请求 409 PROJECT_NOT_ACTIVE 被拦截器提示。

## 下一子项目预告（不在本计划内）

- F4：属性面板（选中节点/边 → 详情 + 编辑 ext_props/描述/优先级/strength）+ 影响分析着色 + 关键路径/环高亮。
- F5：SQL 导入对话框 + 文件导入导出入口。




