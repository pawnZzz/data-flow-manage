# 任务血缘工具 前端 F3b：X6 画布变更 — 设计文档

**日期：** 2026-06-09
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§5.4/5.5 节点·边、§6.4 父子、§7.4 交互→API）
**前置：** 前端 F1/F2/F3a（只读画布），后端 Phase 1-3 全部完成。

## 背景

F3 拆 F3a（只读）/ F3b（变更）。F3a 已能渲染/布局/过滤/选中。**F3b** 让画布可编辑：建节点、连线建边、设/解父、删节点边，全部 editor+。

## 目标

在 F3a 画布上加变更能力，复用其 graphController/GraphCanvas/graphStore。

## 范围

**做：**
- 工具条"新建节点"（name + type 选 schema）→ POST /nodes。
- X6 connecting 拖连建边 → POST /edges（成环预警、冲突撤销视觉边）。
- 右键节点菜单：删除 / 设父节点（下拉选）/ 解除父；右键边菜单：删除。
- 任何变更成功 → graphStore.loadGraph 重拉同步。
- 编辑入口按 projectStore.can('editor') 显隐；viewer 退回 F3a 只读。

**不做（留 F4/F5）：**
- 节点/边属性面板编辑（ext_props/描述/优先级/strength 等改）、影响分析着色、关键路径/环高亮、SQL/文件导入入口。
- X6 embedding 拖入容器建父子（改用下拉选父，避风险）。

## 决策（已与用户确认）

- **设父子 UX**：下拉选父节点（非 X6 embedding）；带解除父。
- **操作入口**：右键节点/边上下文菜单 + 工具条"新建节点"；边由节点间拖连创建。
- **变更后重拉**：任何写成功 → loadGraph 重新同步（后端权威；已有节点位置由 viewPrefs 保留，新节点走布局）。
- **边方向**（master §5.5/§7.4）：从节点 A 拖到 B = "A 依赖 B"，箭头 A→B（POST /edges {source_id:A, target_id:B}）。
- **RBAC**：编辑入口仅 can('editor') 启用；后端仍是唯一权威（editor+ 写、require_active）。
- **拖连即触发**：edge:connected 后移除临时视觉边，由重拉统一渲染（画面以后端为准）。

## 后端写契约（对齐）

| 操作 | 端点 | 错误 |
|------|------|------|
| 建节点 | POST /projects/:pid/nodes {name,type,...} → NodeResponse(201) | type 无 schema→422；name 重复→409 |
| 删节点 | DELETE /projects/:pid/nodes/:nid → 204（DETACH） | 404 |
| 建边 | POST /projects/:pid/edges {source_id,target_id,edge_type,...} → {edge,warnings:{creates_cycle}} | 端点不存在 404；重复 409 EDGE_EXISTS；自环 422 SELF_LOOP |
| 删边 | DELETE /projects/:pid/edges/:eid → 204 | 404 |
| 设父 | POST /projects/:pid/nodes/:nid/parent {parent_id} → 204 | 404；成环/自环 422 PARENT_CYCLE |
| 解父 | DELETE /projects/:pid/nodes/:nid/parent → 204 | 404 |

均 editor+ 且 require_active（归档项目 409 PROJECT_NOT_ACTIVE）。

## 1. 文件结构

```
src/
├── api/edges.ts                 # 新建：createEdge/deleteEdge
├── api/nodes.ts                 # 改：加 createNode/deleteNode/setParent/clearParent
├── stores/graph.ts              # 改：记 currentPid；加 6 个 mutation actions（成功后 loadGraph）
├── components/graph/
│   ├── graphController.ts       # 改：setEditable/enableConnecting/onEdgeConnected/removeEdgeCell/onNodeContextmenu/onEdgeContextmenu
│   ├── GraphCanvas.vue          # 改：editable prop + 新 emits（edgeConnected/nodeContextmenu/edgeContextmenu）
│   ├── NodeContextMenu.vue      # 新建：右键浮层菜单（node/edge kind）
│   ├── CreateNodeDialog.vue     # 新建：建节点对话框（name+type）
│   └── SetParentDialog.vue      # 新建：选父节点对话框
├── views/GraphView.vue          # 改：工具条新建、菜单/对话框接线、编辑事件→store actions
```

## 2. API

**`api/edges.ts`**（新）：
```ts
import { http } from "./client"
import type { GraphEdge } from "@/types/graph"
interface CreateEdgeResponse { edge: GraphEdge; warnings: { creates_cycle: boolean } }
export const edgesApi = {
  create: (pid: number, body: { source_id: string; target_id: string; edge_type?: string }) =>
    http.post(`/projects/${pid}/edges`, body) as unknown as Promise<CreateEdgeResponse>,
  remove: (pid: number, eid: string) =>
    http.delete(`/projects/${pid}/edges/${eid}`) as unknown as Promise<void>,
}
```
**`api/nodes.ts`**（改，加）：
```ts
create: (pid: number, body: { name: string; type: string }) =>
  http.post(`/projects/${pid}/nodes`, body) as unknown as Promise<NodeResponse>,
remove: (pid: number, nid: string) =>
  http.delete(`/projects/${pid}/nodes/${nid}`) as unknown as Promise<void>,
setParent: (pid: number, nid: string, parent_id: string) =>
  http.post(`/projects/${pid}/nodes/${nid}/parent`, { parent_id }) as unknown as Promise<void>,
clearParent: (pid: number, nid: string) =>
  http.delete(`/projects/${pid}/nodes/${nid}/parent`) as unknown as Promise<void>,
```
（保留 F3a 已有的 `list`。）

## 3. graphStore 改

- 加 `currentPid = ref<number|null>(null)`；`loadGraph(pid)` 开头 `currentPid.value = pid`。
- 加 mutation actions（用 `currentPid`；api 错误冒泡，由 client 拦截器 toast）：
```ts
async function createNode(body) { const n = await nodesApi.create(pid, body); await loadGraph(pid); return n }
async function deleteNode(nid)  { await nodesApi.remove(pid, nid); await loadGraph(pid) }
async function createEdge(body) { const r = await edgesApi.create(pid, body); await loadGraph(pid); return r }  // r.warnings 透传
async function deleteEdge(eid)  { await edgesApi.remove(pid, eid); await loadGraph(pid) }
async function setParent(nid, parentId) { await nodesApi.setParent(pid, nid, parentId); await loadGraph(pid) }
async function clearParent(nid) { await nodesApi.clearParent(pid, nid); await loadGraph(pid) }
```
（`pid` = `currentPid.value`；若为 null 抛错或 no-op。）

## 4. graphController 改（X6 编辑）

```ts
setEditable(on: boolean): void          // on=true 启 connecting + nodeMovable；false 关 connecting
enableConnecting(): void                // 内部：graph.options connecting 允许节点间拖连、不允许空白
onEdgeConnected(cb: (sourceId: string, targetId: string, edgeId: string) => void): void  // 'edge:connected'
removeEdgeCell(edgeId: string): void    // 移除临时视觉边
onNodeContextmenu(cb: (id: string, x: number, y: number) => void): void   // 'node:contextmenu'
onEdgeContextmenu(cb: (id: string, x: number, y: number) => void): void   // 'edge:contextmenu'
```
- `edge:connected` 事件取新边的 source/target node id + 该 X6 边 id。X6 v3 connecting 配置：`{ allowBlank:false, allowLoop:false, allowMulti:false, router:'normal' }`（allowLoop/Multi 前端先挡，后端仍权威）。
- contextmenu 回调把 `e.clientX/clientY` 作为屏幕坐标传出供菜单定位。
- `setEditable` 在 init 后调；`init` 默认不启 connecting（F3a 只读保持）。

## 5. GraphCanvas 改

- 新 prop `editable: boolean`；onMounted 后 `controller.setEditable(editable)`，watch editable 同步。
- editable 时注册 `onEdgeConnected`/`onNodeContextmenu`/`onEdgeContextmenu` → emit。
- 新 emits：`edgeConnected:[sourceId,targetId,edgeId]`、`nodeContextmenu:[id,x,y]`、`edgeContextmenu:[id,x,y]`。
- 既有 select/nodeMoved/expose 不变。

## 6. 数据流

```
工具条"新建节点"(editable) → 先 schemasApi.list(pid) → CreateNodeDialog(schemas)
  → 提交 {name,type} → store.createNode → reload
拖连边 → emit edgeConnected(sid,tid,edgeId)
  → GraphView: controller? 不直接持有；改由 GraphCanvas 内部先 removeEdgeCell(edgeId) 再 emit
    （即 GraphCanvas 收到 edge:connected 即移除临时边并 emit；GraphView 只管调 API）
  → store.createEdge({source_id:sid,target_id:tid})
    → warnings.creates_cycle ? ElMessage.warning("创建后形成环") : 静默；reload 已在 action
    → 409/422 → 拦截器 toast（临时边已移除）
右键节点 → emit nodeContextmenu(id,x,y) → GraphView 显 NodeContextMenu(node,x,y)
  → 删除 confirm → store.deleteNode(id)
  → 设父 → SetParentDialog(candidates=sidebarNodes 排除自身) → store.setParent(id,parentId)
  → 解父 → store.clearParent(id)
右键边 → emit edgeContextmenu(id,x,y) → NodeContextMenu(edge,x,y) → 删除 confirm → store.deleteEdge(id)
```
> 临时边移除职责放 GraphCanvas（紧挨 edge:connected，避免 GraphView 触达 controller 实例）。GraphCanvas 在 onEdgeConnected 回调里先 `controller.removeEdgeCell(edgeId)` 再 `emit('edgeConnected', sid, tid, edgeId)`。

## 7. 组件

**CreateNodeDialog.vue**：el-dialog；name 输入（必填）+ type el-select（props `schemas: NodeTypeSchema[]`，选项 type_key/display_name；schemas 空时提示"请先在 Schema 管理建类型"并禁用提交）。提交 emit `{name, type}`。

**SetParentDialog.vue**：el-dialog；el-select 列候选父（props `candidates: {id:string; name:string}[]`，已由 GraphView 排除自身）。提交 emit `parentId`。

**NodeContextMenu.vue**：绝对定位浮层（props `visible, x, y, kind:'node'|'edge'`）。node→删除/设父节点/解除父；edge→删除。点项 emit `delete`/`setParent`/`clearParent`；点外部或 Esc emit `close`。纯展示。

**GraphView.vue 改**：工具条加"新建节点"按钮（`v-if="proj.can('editor')"`）；`:editable="proj.can('editor')"` 传 GraphCanvas；接 edgeConnected/nodeContextmenu/edgeContextmenu → store actions / 菜单 / 对话框；删除均 `ElMessageBox.confirm`。

## 8. 测试（mock api/store/controller）

- `graph.store.mutations.spec.ts`：6 actions 各调对应 api 且成功后调 loadGraph(currentPid)；createEdge 透传 warnings；api 抛错时不调 loadGraph、错误冒泡；currentPid 由 loadGraph 设置。
- `CreateNodeDialog.spec.ts`：渲染 type 选项；name 必填；提交 emit {name,type}；空 schemas 提示+禁用。
- `SetParentDialog.spec.ts`：渲染候选；提交 emit parentId。
- `NodeContextMenu.spec.ts`：node kind 显删除/设父/解父，edge kind 只删除；点项 emit 对应动作；visible 控制显隐。
- `GraphCanvas.spec.ts`（改）：editable=true onMounted 调 setEditable(true) + 注册 edgeConnected/contextmenu 回调；editable=false → setEditable(false) 不注册编辑；edge:connected 回调 → removeEdgeCell + emit edgeConnected。
- `GraphView.mutations.spec.ts`（stub GraphCanvas/对话框/菜单）：can('editor') 才显"新建节点"；edgeConnected → store.createEdge；nodeContextmenu → 菜单显现；删除 confirm → store.deleteNode；viewer 无编辑入口。

## Definition of Done

- `npm run build`（vue-tsc）通过、无 TS 错误。
- `npm run test` 全绿（F1+F2+F3a 既有 69 + F3b 新增）。
- 手动（editor 身份）：工具条新建节点（选 type）→ 出现；节点间拖连建边（成环弹预警；重复/自环被拒并撤销视觉边）；右键节点删除/设父（下拉）/解父；右键边删除；每次变更后画布重拉同步、已有节点位置保留。
- viewer 身份：无任何编辑入口（工具条无新建、无右键编辑菜单、不能拖连），退回 F3a 只读。
- 归档项目：编辑请求 409 PROJECT_NOT_ACTIVE 被拦截器提示。

## 下一子项目预告（不在本计划内）

- F4：属性面板（选中节点/边 → GET 详情 + 编辑 ext_props/描述/优先级/strength 等）+ 影响分析着色 + 关键路径/环高亮。
- F5：SQL 导入对话框 + 文件导入导出入口。


