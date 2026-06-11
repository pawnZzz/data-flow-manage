# 任务血缘工具 前端 F3a：X6 画布（只读核心）— 设计文档

**日期：** 2026-06-09
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§5.6 图查询、§6.5 子图、§7.2-7.6 画布/渲染契约）
**前置：** 前端 F1（地基）、F2（项目/成员/Schema），后端 Phase 1-3 全部完成。

## 背景与拆分

前端 F1-F5。F3（画布）体量最重，拆为：
- **F3a（本文档）**：只读画布核心——渲染、布局、平移缩放选中、侧栏树/过滤、布局位置持久化。
- F3b：画布变更（建节点 name+type、连线建边、拖入建父子、删节点/边）。
- F4：属性面板 + 影响分析可视化。F5：SQL/文件导入入口。

## 目标

在 ProjectLayout 内加 X6 画布作为项目主视图，只读渲染项目全图并支持浏览/过滤/布局持久化。

## 范围

**做：**
- `GET /graph`（全图）渲染节点/边；`GET /nodes`（完整）驱动侧栏 NodeTree + FilterBar。
- X6：dagre 自动布局、平移/缩放/框选、节点按 type 着色 + is_critical 描边 + priority 标签。
- 侧栏过滤/点击 → 画布高亮匹配、置灰其余、居中选中。
- 选中节点 → graph store 记 selectedId（F4 接面板）。
- 手拖位置 + 视口存 localStorage（key=project+user），重进恢复；"重新布局"重跑 dagre 并清持久位置。

**不做（留后续）：**
- 建/改/删节点边、连线建边、拖入建父子、右键菜单（F3b）。
- 属性面板、影响分析着色、关键路径/环高亮（F4）。
- SQL/文件导入入口（F5）。

## 决策（已与用户确认）

- **F3 拆 F3a 只读 / F3b 变更**：本期只 F3a。
- **过滤数据源**：侧栏 `GET /nodes`（完整字段），画布 `GET /graph`（精简拓扑）；过滤在已加载 sidebarNodes 上算 matchedIds，画布按 id 高亮/置灰，不重新请求。
- **画布为 `/projects/:pid` 主视图**：`""` 子路由从重定向 members 改为 GraphView。
- **加载全项目图**（GET /graph 无 center）；节点按 type 着色、is_critical 描边、priority 标签。
- **选中仅高亮 + 暴露 id**（属性面板留 F4）。
- **布局**：自动 dagre + 手拖位置持久化 localStorage（project+user key）。
- **X6 测试策略**：纯逻辑抽模块单测，X6 实例命令集中 graphController（组件测试 mock 之，不真渲）。

## 后端契约（对齐）

- `GET /api/v1/projects/:pid/graph?center=&depth=&direction=` → `{nodes:[{id,name,type,priority,is_critical,parent_id}], edges:[EdgeResponse], stats:{node_count,edge_count,has_cycle}}`。F3a 不传 center（全图）。
- `GET /api/v1/projects/:pid/nodes?type=&department=&system=&priority=&tag=&name=` → `NodeResponse[]`（完整：含 department/system/tags/parent_id 等）。F3a 拉全量供侧栏，过滤在前端做。
- 均 viewer+。

## 新依赖

`@antv/x6@^3`、`@antv/layout@^2`（dagre 布局）。

## 1. 文件结构

```
src/
├── api/
│   ├── graph.ts                 # getSubgraph(pid,{center?,depth?,direction?}) → Subgraph
│   └── nodes.ts                 # listNodes(pid, filters?) → NodeResponse[]
├── stores/graph.ts              # subgraph + sidebarNodes + selectedId + filters + matchedIds
├── views/GraphView.vue          # 画布主视图：加载数据，组合 GraphCanvas + 侧栏
├── components/graph/
│   ├── GraphCanvas.vue          # X6 容器挂载 + 事件 → graphController
│   ├── graphController.ts       # X6 Graph 命令封装（薄；组件测试 mock）
│   ├── nodeShapes.ts            # 纯：GraphSubgraphNode → X6 节点配置
│   ├── layout.ts                # 纯：nodes+edges → dagre 位置 map（@antv/layout）
│   └── viewPrefs.ts             # 纯：localStorage 读写位置/视口（project+user key）
├── components/sidebar/
│   ├── NodeTree.vue             # 父子树（GET /nodes）
│   └── FilterBar.vue            # 多维过滤控件
├── types/graph.ts               # 改：加 GraphEdge/GraphSubgraphNode/GraphStats/Subgraph/XYPos/NodeResponse
└── router/index.ts              # 改：/projects/:pid "" 子路由 → GraphView
```

## 2. 类型补充（`types/graph.ts`）

```ts
export interface GraphEdge {
  id: string; project_id: number; source_id: string; target_id: string
  edge_type: string; description: string | null; is_required: boolean
  strength: string; ext_props: Record<string, unknown>; created_at: string; created_by: number
}
export interface GraphSubgraphNode {
  id: string; name: string; type: string; priority: string | null; is_critical: boolean; parent_id: string | null
}
export interface GraphStats { node_count: number; edge_count: number; has_cycle: boolean }
export interface Subgraph { nodes: GraphSubgraphNode[]; edges: GraphEdge[]; stats: GraphStats }
export interface XYPos { x: number; y: number }

// 完整节点（侧栏用），对齐后端 NodeResponse 子集（F3a 需要的字段）
export interface NodeResponse {
  id: string; project_id: number; name: string; type: string
  description: string | null; owner: string | null; department: string | null
  system: string | null; priority: string | null; tags: string[]
  ext_props: Record<string, unknown>; is_critical: boolean
  parent_id: string | null; children_count: number
  upstream_count: number; downstream_count: number
}
export interface NodeFilters {
  type?: string; department?: string; system?: string; priority?: string; tag?: string; name?: string
}
```

## 3. API 模块

```ts
// api/graph.ts
import { http } from "./client"
import type { Subgraph } from "@/types/graph"
export const graphApi = {
  getSubgraph: (pid: number, params: { center?: string; depth?: number; direction?: string } = {}) =>
    http.get(`/projects/${pid}/graph`, { params }) as unknown as Promise<Subgraph>,
}

// api/nodes.ts
import { http } from "./client"
import type { NodeFilters, NodeResponse } from "@/types/graph"
export const nodesApi = {
  list: (pid: number, filters: NodeFilters = {}) =>
    http.get(`/projects/${pid}/nodes`, { params: filters }) as unknown as Promise<NodeResponse[]>,
}
```

## 4. `stores/graph.ts`（Pinia setup store）

- state：`subgraph: Subgraph | null`、`sidebarNodes: NodeResponse[]`、`selectedId: string | null`、`filters: NodeFilters`。
- getter `matchedIds: Set<string> | null`：filters 全空 → `null`（全亮）；否则在 sidebarNodes 上逐条匹配（type 精确、department/system 精确、priority 精确、tag in tags、name 子串不分大小写），返回匹配 id 集合。
- actions：
  - `loadGraph(pid)`：`Promise.all([graphApi.getSubgraph(pid), nodesApi.list(pid)])` → 填 subgraph + sidebarNodes。
  - `select(id: string | null)`、`setFilter(patch: Partial<NodeFilters>)`、`clearFilters()`、`clear()`。

## 5. 数据流

```
GraphView.onMounted(pid) → graphStore.loadGraph(pid)        # 并发 /graph + /nodes
  → GraphCanvas props=subgraph
      → controller.setData(nodeShapes.toXNode 映射, edges)
      → 有持久位置 ? controller.applyPositions(saved) : controller.runLayout()
      → controller.applyMatch(matchedIds)
  → 侧栏 NodeTree/FilterBar 用 sidebarNodes
交互：
  点画布节点 → GraphCanvas emit select → store.select → controller.highlightSelected
  改 FilterBar → store.setFilter → matchedIds 变 → GraphCanvas watch → controller.applyMatch
  点 NodeTree → store.select → controller.centerOn + highlightSelected
  拖节点 → GraphCanvas 监听 node:moved → viewPrefs.savePos(pid,uid,id,xy)
  平移/缩放 → 防抖 viewPrefs.saveViewport(pid,uid,vp)
  "重新布局" → controller.runLayout() + viewPrefs.clear(pid,uid)
```

## 6. graphController 契约（`graphController.ts`）

```ts
export class GraphController {
  init(container: HTMLElement): void
  setData(nodes: XNode[], edges: XEdge[]): void
  applyPositions(pos: Record<string, XYPos>): void
  runLayout(): Record<string, XYPos>          // 调 layout.dagre，套用并返回位置
  highlightSelected(id: string | null): void
  applyMatch(ids: Set<string> | null): void    // null=全亮；否则匹配亮、其余置灰
  centerOn(id: string): void
  getViewport(): { zoom: number; tx: number; ty: number }
  setViewport(vp: { zoom: number; tx: number; ty: number }): void
  onNodeMoved(cb: (id: string, xy: XYPos) => void): void
  onNodeClick(cb: (id: string) => void): void
  dispose(): void
}
```

**纯模块**：
- `nodeShapes.toXNode(n: GraphSubgraphNode): XNode`：fill 按 type（分类调色板，稳定 hash→色板索引）、is_critical 加红描边、label = name（+ priority 角标）。
- `layout.dagre(nodes, edges): Record<string, XYPos>`：用 `@antv/layout` 的 DagreLayout，rankdir TB，返回每节点 {x,y}。
- `viewPrefs`：`key(pid,uid)='graph:{pid}:{uid}'`；`savePos/saveViewport/read/clear`，存 `{positions: Record<id,XYPos>, viewport?}`。uid 从 auth store `user.id`。

## 7. 侧栏组件

**FilterBar.vue**：type（el-select，选项=sidebarNodes 去重 type）、department/system（el-select 或输入）、priority（P0-P5 select）、tag（输入）、name（搜索框）。改动 → emit/`store.setFilter`；清空按钮 → `clearFilters`。不重新请求，仅驱动 matchedIds。

**NodeTree.vue**：用 sidebarNodes 按 parent_id 构树（无父=顶层）→ el-tree。项显示 name + priority 标签 + is_critical 标记；受 matchedIds 过滤（不匹配置灰/隐藏）。点击项 → emit select(id)。

## 8. 测试策略（X6 难纯测 → 重纯模块 + mock controller）

- `nodeShapes.spec.ts`（纯）：type→fill 稳定映射、is_critical→红描边、label 含 name/priority。
- `layout.spec.ts`（纯）：nodes+edges → 每 id 有 {x,y}（键齐全、非 NaN）。
- `viewPrefs.spec.ts`（纯，mock localStorage）：savePos/saveViewport/read/clear 往返；key 含 pid+uid。
- `graph.store.spec.ts`：loadGraph 并发填 subgraph+sidebarNodes；matchedIds 各维度边界（type/priority/department/tag/name、空 filters→null）；select/setFilter/clearFilters/clear。
- `FilterBar.spec.ts`：改控件 emit/setFilter 携正确 patch；清空。
- `NodeTree.spec.ts`：sidebarNodes→树结构；点击 emit select；matchedIds 过滤显隐。
- `GraphCanvas.spec.ts`：**vi.mock graphController**——验 props(subgraph)→controller.setData 调用；node:click→emit select；matchedIds 变→applyMatch 调用；卸载→dispose。不真渲 X6。
- `GraphView.spec.ts`：mock store + stub 子组件——onMounted 调 loadGraph(pid)、组合 canvas+侧栏。
- `graphController.ts` 自身不单元测（X6 真实例难测）；靠组件层 mock 覆盖契约 + 手动验收。标注于文件注释。

## Definition of Done

- `npm run build`（vue-tsc）通过、无 TS 错误（含 @antv/x6 类型）。
- `npm run test` 全绿（F1+F2 既有 39 + F3a 新增）。
- 手动：进项目 → 画布渲染全图（dagre 布局、type 着色、is_critical 高亮、priority 标签）→ 平移/缩放/选中 → 侧栏树点击居中 → FilterBar 过滤画布高亮/置灰 → 手拖节点刷新后位置保留 → "重新布局"重排并清持久位置。
- 画布是 `/projects/:pid` 主视图；空图显示空状态。

## 下一子项目预告（不在本计划内）

- F3b：画布变更（建节点 name+type、连线建边、拖入建父子、删节点/边）——复用 F3a 的 controller/store。
- F4：属性面板（选中节点/边 → GET 详情 + 编辑）+ 影响分析着色 + 关键路径/环高亮。
- F5：SQL 导入对话框 + 文件导入导出入口。


