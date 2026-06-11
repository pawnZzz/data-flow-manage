# 前端 F3a：X6 画布（只读核心）— Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 ProjectLayout 内加 X6 画布只读主视图：GET /graph 渲染 + dagre 布局 + 平移缩放选中 + 侧栏 NodeTree/FilterBar 过滤 + 布局位置 localStorage 持久化。

**Architecture:** 纯逻辑抽模块（nodeShapes/layout/viewPrefs/store matchedIds）单测；X6 实例命令集中 graphController（薄封装，组件测试 mock，不真渲）。画布 GET /graph、侧栏 GET /nodes 双数据源；过滤纯前端。

**Tech Stack:** Vue 3(`<script setup>`+TS)、Pinia、Element Plus、@antv/x6@3、@antv/layout@2、Vitest、@vue/test-utils。

参考 spec：`docs/superpowers/specs/2026-06-09-frontend-f3a-canvas-readonly-design.md`。

---

## File Structure

- `frontend/package.json` — 改：加 `@antv/x6`、`@antv/layout`。
- `frontend/src/types/graph.ts` — 改：加 GraphEdge/GraphSubgraphNode/GraphStats/Subgraph/XYPos/NodeResponse/NodeFilters。
- `frontend/src/api/graph.ts`、`frontend/src/api/nodes.ts` — 新建。
- `frontend/src/stores/graph.ts` — 新建：subgraph/sidebarNodes/selectedId/filters/matchedIds。
- `frontend/src/components/graph/nodeShapes.ts`、`layout.ts`、`viewPrefs.ts` — 新建：纯模块。
- `frontend/src/components/graph/graphController.ts`、`GraphCanvas.vue` — 新建：X6 封装 + 组件。
- `frontend/src/components/sidebar/FilterBar.vue`、`NodeTree.vue` — 新建。
- `frontend/src/views/GraphView.vue` — 新建：画布主视图。
- `frontend/src/router/index.ts` — 改：`/projects/:pid` 的 `""` 子路由 → GraphView。
- 测试：各 .spec.ts。

约定：命令在 `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend` 下跑；commit 在仓库根；message 末尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。`@`→src。

## Task 1: 依赖 + 类型 + API + graph store

**Files:**
- Modify: `frontend/package.json`, `frontend/src/types/graph.ts`
- Create: `frontend/src/api/graph.ts`, `frontend/src/api/nodes.ts`, `frontend/src/stores/graph.ts`
- Test: `frontend/tests/graph.store.spec.ts`

- [ ] **Step 1: 加依赖**

在 `frontend/package.json` 的 `dependencies` 加 `"@antv/x6": "^3.1.0"` 与 `"@antv/layout": "^2.0.0"`（注意逗号），然后：
```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm install 2>&1 | tail -3
```

- [ ] **Step 2: 追加类型到 `frontend/src/types/graph.ts`（文件末尾）**

```ts
export interface GraphEdge {
  id: string
  project_id: number
  source_id: string
  target_id: string
  edge_type: string
  description: string | null
  is_required: boolean
  strength: string
  ext_props: Record<string, unknown>
  created_at: string
  created_by: number
}

export interface GraphSubgraphNode {
  id: string
  name: string
  type: string
  priority: string | null
  is_critical: boolean
  parent_id: string | null
}

export interface GraphStats {
  node_count: number
  edge_count: number
  has_cycle: boolean
}

export interface Subgraph {
  nodes: GraphSubgraphNode[]
  edges: GraphEdge[]
  stats: GraphStats
}

export interface XYPos {
  x: number
  y: number
}

export interface NodeResponse {
  id: string
  project_id: number
  name: string
  type: string
  description: string | null
  owner: string | null
  department: string | null
  system: string | null
  priority: string | null
  tags: string[]
  ext_props: Record<string, unknown>
  is_critical: boolean
  parent_id: string | null
  children_count: number
  upstream_count: number
  downstream_count: number
}

export interface NodeFilters {
  type?: string
  department?: string
  system?: string
  priority?: string
  tag?: string
  name?: string
}
```

- [ ] **Step 3: 创建 `frontend/src/api/graph.ts`**

```ts
import { http } from "./client"
import type { Subgraph } from "@/types/graph"

export const graphApi = {
  getSubgraph: (pid: number, params: { center?: string; depth?: number; direction?: string } = {}) =>
    http.get(`/projects/${pid}/graph`, { params }) as unknown as Promise<Subgraph>,
}
```

- [ ] **Step 4: 创建 `frontend/src/api/nodes.ts`**

```ts
import { http } from "./client"
import type { NodeFilters, NodeResponse } from "@/types/graph"

export const nodesApi = {
  list: (pid: number, filters: NodeFilters = {}) =>
    http.get(`/projects/${pid}/nodes`, { params: filters }) as unknown as Promise<NodeResponse[]>,
}
```

- [ ] **Step 5: 创建 `frontend/src/stores/graph.ts`**

```ts
import { computed, ref } from "vue"
import { defineStore } from "pinia"
import { graphApi } from "@/api/graph"
import { nodesApi } from "@/api/nodes"
import type { NodeFilters, NodeResponse, Subgraph } from "@/types/graph"

export const useGraphStore = defineStore("graph", () => {
  const subgraph = ref<Subgraph | null>(null)
  const sidebarNodes = ref<NodeResponse[]>([])
  const selectedId = ref<string | null>(null)
  const filters = ref<NodeFilters>({})

  const hasFilter = computed(() =>
    Object.values(filters.value).some((v) => v !== undefined && v !== ""),
  )

  function nodeMatches(n: NodeResponse, f: NodeFilters): boolean {
    if (f.type && n.type !== f.type) return false
    if (f.department && n.department !== f.department) return false
    if (f.system && n.system !== f.system) return false
    if (f.priority && n.priority !== f.priority) return false
    if (f.tag && !n.tags.includes(f.tag)) return false
    if (f.name && !n.name.toLowerCase().includes(f.name.toLowerCase())) return false
    return true
  }

  const matchedIds = computed<Set<string> | null>(() => {
    if (!hasFilter.value) return null
    const ids = new Set<string>()
    for (const n of sidebarNodes.value) {
      if (nodeMatches(n, filters.value)) ids.add(n.id)
    }
    return ids
  })

  async function loadGraph(pid: number) {
    const [sg, nodes] = await Promise.all([graphApi.getSubgraph(pid), nodesApi.list(pid)])
    subgraph.value = sg
    sidebarNodes.value = nodes
  }

  function select(id: string | null) {
    selectedId.value = id
  }
  function setFilter(patch: Partial<NodeFilters>) {
    filters.value = { ...filters.value, ...patch }
  }
  function clearFilters() {
    filters.value = {}
  }
  function clear() {
    subgraph.value = null
    sidebarNodes.value = []
    selectedId.value = null
    filters.value = {}
  }

  return {
    subgraph, sidebarNodes, selectedId, filters,
    matchedIds, loadGraph, select, setFilter, clearFilters, clear,
  }
})
```

- [ ] **Step 6: 写测试 `frontend/tests/graph.store.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"

const graphApi = vi.hoisted(() => ({ getSubgraph: vi.fn() }))
const nodesApi = vi.hoisted(() => ({ list: vi.fn() }))
vi.mock("@/api/graph", () => ({ graphApi }))
vi.mock("@/api/nodes", () => ({ nodesApi }))

import { useGraphStore } from "@/stores/graph"

const SG = { nodes: [{ id: "a", name: "a", type: "t", priority: null, is_critical: false, parent_id: null }], edges: [], stats: { node_count: 1, edge_count: 0, has_cycle: false } }
const NODES = [
  { id: "a", project_id: 1, name: "alpha", type: "data_task", description: null, owner: null, department: "dw", system: null, priority: "P1", tags: ["core"], ext_props: {}, is_critical: false, parent_id: null, children_count: 0, upstream_count: 0, downstream_count: 0 },
  { id: "b", project_id: 1, name: "beta", type: "service", description: null, owner: null, department: "ops", system: null, priority: "P3", tags: [], ext_props: {}, is_critical: false, parent_id: null, children_count: 0, upstream_count: 0, downstream_count: 0 },
]

beforeEach(() => {
  setActivePinia(createPinia())
  graphApi.getSubgraph.mockReset()
  nodesApi.list.mockReset()
})

it("loadGraph 并发填 subgraph + sidebarNodes", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  expect(s.subgraph?.nodes.length).toBe(1)
  expect(s.sidebarNodes.length).toBe(2)
})

it("无 filter 时 matchedIds 为 null（全亮）", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  expect(s.matchedIds).toBeNull()
})

it("按 type 过滤算 matchedIds", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  s.setFilter({ type: "data_task" })
  expect([...(s.matchedIds as Set<string>)]).toEqual(["a"])
})

it("按 name 子串 + priority + department + tag 过滤", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  s.setFilter({ name: "ALP" })
  expect([...(s.matchedIds as Set<string>)]).toEqual(["a"])
  s.clearFilters()
  s.setFilter({ tag: "core" })
  expect([...(s.matchedIds as Set<string>)]).toEqual(["a"])
  s.clearFilters()
  s.setFilter({ department: "ops" })
  expect([...(s.matchedIds as Set<string>)]).toEqual(["b"])
})

it("select / clear", async () => {
  graphApi.getSubgraph.mockResolvedValue(SG)
  nodesApi.list.mockResolvedValue(NODES)
  const s = useGraphStore()
  await s.loadGraph(1)
  s.select("a")
  expect(s.selectedId).toBe("a")
  s.clear()
  expect(s.subgraph).toBeNull()
  expect(s.selectedId).toBeNull()
})
```

- [ ] **Step 7: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -8`
Expected: 全绿（F1+F2 既有 39 + 本任务 5 = 44）。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/package.json frontend/package-lock.json frontend/src/types/graph.ts frontend/src/api/graph.ts frontend/src/api/nodes.ts frontend/src/stores/graph.ts frontend/tests/graph.store.spec.ts
git commit -m "feat(frontend): F3a 图类型、graph/nodes API 与 graph store（matchedIds 过滤）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

Do NOT run `npm run build`（GraphView 等在后续任务，router 暂未接）. 

## Task 2: 纯模块 nodeShapes + layout + viewPrefs

**Files:**
- Create: `frontend/src/components/graph/nodeShapes.ts`, `frontend/src/components/graph/layout.ts`, `frontend/src/components/graph/viewPrefs.ts`
- Test: `frontend/tests/nodeShapes.spec.ts`, `frontend/tests/layout.spec.ts`, `frontend/tests/viewPrefs.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/components/graph/nodeShapes.ts`**

```ts
import type { GraphSubgraphNode, XYPos } from "@/types/graph"

const PALETTE = ["#5B8FF9", "#5AD8A6", "#5D7092", "#F6BD16", "#E8684A", "#6DC8EC", "#9270CA", "#FF9D4D"]

// 稳定地把 type 串映射到调色板索引（同 type 同色，跨会话稳定）
export function colorForType(type: string): string {
  let h = 0
  for (let i = 0; i < type.length; i++) h = (h * 31 + type.charCodeAt(i)) >>> 0
  return PALETTE[h % PALETTE.length]
}

export interface XNode {
  id: string
  x: number
  y: number
  width: number
  height: number
  label: string
  attrs: { body: { fill: string; stroke: string; strokeWidth: number } }
}

export function toXNode(n: GraphSubgraphNode, pos: XYPos = { x: 0, y: 0 }): XNode {
  const label = n.priority ? `${n.name} [${n.priority}]` : n.name
  return {
    id: n.id,
    x: pos.x,
    y: pos.y,
    width: 160,
    height: 40,
    label,
    attrs: {
      body: {
        fill: colorForType(n.type),
        stroke: n.is_critical ? "#F5222D" : "#C2C8D5",
        strokeWidth: n.is_critical ? 3 : 1,
      },
    },
  }
}
```

- [ ] **Step 2: 写测试 `frontend/tests/nodeShapes.spec.ts`**

```ts
import { it, expect } from "vitest"
import { colorForType, toXNode } from "@/components/graph/nodeShapes"

const NODE = { id: "n1", name: "ods", type: "data_task", priority: "P1", is_critical: false, parent_id: null }

it("colorForType 同 type 稳定同色", () => {
  expect(colorForType("data_task")).toBe(colorForType("data_task"))
})

it("不同 type 一般不同色（不强制，但取自调色板）", () => {
  const c = colorForType("service")
  expect(typeof c).toBe("string")
  expect(c.startsWith("#")).toBe(true)
})

it("toXNode label 含 name 与 priority", () => {
  const x = toXNode(NODE)
  expect(x.label).toBe("ods [P1]")
  expect(x.id).toBe("n1")
})

it("toXNode 无 priority 时 label 只 name", () => {
  const x = toXNode({ ...NODE, priority: null })
  expect(x.label).toBe("ods")
})

it("is_critical 加红描边加粗", () => {
  const x = toXNode({ ...NODE, is_critical: true })
  expect(x.attrs.body.stroke).toBe("#F5222D")
  expect(x.attrs.body.strokeWidth).toBe(3)
})

it("toXNode 套用传入位置", () => {
  const x = toXNode(NODE, { x: 10, y: 20 })
  expect([x.x, x.y]).toEqual([10, 20])
})
```

- [ ] **Step 3: 创建 `frontend/src/components/graph/layout.ts`**

```ts
import { DagreLayout } from "@antv/layout"
import type { GraphEdge, GraphSubgraphNode, XYPos } from "@/types/graph"

// 用 dagre 计算分层布局，返回 {nodeId: {x,y}}
export function dagre(nodes: GraphSubgraphNode[], edges: GraphEdge[]): Record<string, XYPos> {
  if (nodes.length === 0) return {}
  const layout = new DagreLayout({
    type: "dagre",
    rankdir: "TB",
    nodesep: 40,
    ranksep: 60,
  })
  const data = {
    nodes: nodes.map((n) => ({ id: n.id })),
    edges: edges.map((e) => ({ source: e.source_id, target: e.target_id })),
  }
  const result = layout.layout(data) as { nodes: { id: string; x: number; y: number }[] }
  const pos: Record<string, XYPos> = {}
  for (const n of result.nodes) pos[n.id] = { x: n.x, y: n.y }
  return pos
}
```

> 注：`@antv/layout@2` 的 `DagreLayout.layout(data)` 返回带 x/y 的节点。若该版本 API 形态不同（如返回 Promise 或就地改 data），实现时按实际调整，保持"输入 nodes+edges、输出 {id:{x,y}}"契约不变，并相应调整测试的 await。

- [ ] **Step 4: 写测试 `frontend/tests/layout.spec.ts`**

```ts
import { it, expect } from "vitest"
import { dagre } from "@/components/graph/layout"

const N = (id: string) => ({ id, name: id, type: "t", priority: null, is_critical: false, parent_id: null })
const E = (s: string, t: string) => ({
  id: `${s}-${t}`, project_id: 1, source_id: s, target_id: t, edge_type: "data_flow",
  description: null, is_required: true, strength: "strong", ext_props: {}, created_at: "", created_by: 1,
})

it("空图返回空位置", () => {
  expect(dagre([], [])).toEqual({})
})

it("每个节点都有非 NaN 坐标", () => {
  const pos = dagre([N("a"), N("b"), N("c")], [E("a", "b"), E("b", "c")])
  for (const id of ["a", "b", "c"]) {
    expect(pos[id]).toBeDefined()
    expect(Number.isFinite(pos[id].x)).toBe(true)
    expect(Number.isFinite(pos[id].y)).toBe(true)
  }
})

it("分层：下游节点 y 大于上游（TB）", () => {
  const pos = dagre([N("a"), N("b")], [E("a", "b")])
  expect(pos.b.y).toBeGreaterThan(pos.a.y)
})
```

> 若 `dagre` 因 @antv/layout v2 是异步而需 `await`，把函数与三个测试改 async/await（契约不变）。实现者按实际 API 定。

- [ ] **Step 5: 创建 `frontend/src/components/graph/viewPrefs.ts`**

```ts
import type { XYPos } from "@/types/graph"

export interface Viewport {
  zoom: number
  tx: number
  ty: number
}
export interface GraphPrefs {
  positions: Record<string, XYPos>
  viewport?: Viewport
}

function key(pid: number, uid: number): string {
  return `graph:${pid}:${uid}`
}

export function read(pid: number, uid: number): GraphPrefs {
  const raw = localStorage.getItem(key(pid, uid))
  if (!raw) return { positions: {} }
  try {
    const parsed = JSON.parse(raw) as GraphPrefs
    return { positions: parsed.positions ?? {}, viewport: parsed.viewport }
  } catch {
    return { positions: {} }
  }
}

export function savePos(pid: number, uid: number, id: string, xy: XYPos): void {
  const prefs = read(pid, uid)
  prefs.positions[id] = xy
  localStorage.setItem(key(pid, uid), JSON.stringify(prefs))
}

export function saveViewport(pid: number, uid: number, vp: Viewport): void {
  const prefs = read(pid, uid)
  prefs.viewport = vp
  localStorage.setItem(key(pid, uid), JSON.stringify(prefs))
}

export function clear(pid: number, uid: number): void {
  localStorage.removeItem(key(pid, uid))
}
```

- [ ] **Step 6: 写测试 `frontend/tests/viewPrefs.spec.ts`**

```ts
import { it, expect, beforeEach } from "vitest"
import { read, savePos, saveViewport, clear } from "@/components/graph/viewPrefs"

beforeEach(() => localStorage.clear())

it("空时返回空 positions", () => {
  expect(read(1, 7)).toEqual({ positions: {} })
})

it("savePos 往返，key 含 pid+uid", () => {
  savePos(1, 7, "a", { x: 5, y: 6 })
  expect(read(1, 7).positions.a).toEqual({ x: 5, y: 6 })
  expect(localStorage.getItem("graph:1:7")).toBeTruthy()
  // 不同 pid/uid 互不干扰
  expect(read(2, 7).positions.a).toBeUndefined()
})

it("saveViewport 往返且不丢已存位置", () => {
  savePos(1, 7, "a", { x: 1, y: 2 })
  saveViewport(1, 7, { zoom: 1.5, tx: 10, ty: 20 })
  const p = read(1, 7)
  expect(p.viewport).toEqual({ zoom: 1.5, tx: 10, ty: 20 })
  expect(p.positions.a).toEqual({ x: 1, y: 2 })
})

it("clear 清除", () => {
  savePos(1, 7, "a", { x: 1, y: 2 })
  clear(1, 7)
  expect(read(1, 7)).toEqual({ positions: {} })
})

it("坏 JSON 容错返回空", () => {
  localStorage.setItem("graph:1:7", "{bad")
  expect(read(1, 7)).toEqual({ positions: {} })
})
```

- [ ] **Step 7: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -10`
Expected: 全绿（44 + 本任务 ~14 = 58 上下；具体数视 layout 是否 async 拆分）。若 `@antv/layout` 导入或 DagreLayout API 与假设不符导致 layout 测试失败，按实际 API 调整 layout.ts + 测试（保持契约），不跳过测试。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/components/graph/nodeShapes.ts frontend/src/components/graph/layout.ts frontend/src/components/graph/viewPrefs.ts frontend/tests/nodeShapes.spec.ts frontend/tests/layout.spec.ts frontend/tests/viewPrefs.spec.ts
git commit -m "feat(frontend): F3a 纯模块 nodeShapes/layout(dagre)/viewPrefs

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 3: graphController（X6 封装）+ GraphCanvas 组件

**Files:**
- Create: `frontend/src/components/graph/graphController.ts`, `frontend/src/components/graph/GraphCanvas.vue`
- Test: `frontend/tests/GraphCanvas.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/components/graph/graphController.ts`**

> 本类是 X6 实例命令的薄封装，依赖真实 DOM/SVG，**不单元测**——契约靠 GraphCanvas 组件层 mock 覆盖 + 手动验收。

```ts
import { Graph } from "@antv/x6"
import type { GraphEdge, GraphSubgraphNode, XYPos } from "@/types/graph"
import { toXNode } from "./nodeShapes"
import { dagre } from "./layout"

export class GraphController {
  private graph: Graph | null = null
  private nodes: GraphSubgraphNode[] = []
  private edges: GraphEdge[] = []

  init(container: HTMLElement): void {
    this.graph = new Graph({
      container,
      autoResize: true,
      panning: true,
      mousewheel: { enabled: true },
      interacting: { nodeMovable: true, edgeMovable: false },
      connecting: { allowBlank: false },
    })
  }

  setData(nodes: GraphSubgraphNode[], edges: GraphEdge[]): void {
    this.nodes = nodes
    this.edges = edges
    if (!this.graph) return
    this.graph.fromJSON({
      nodes: nodes.map((n) => {
        const x = toXNode(n)
        return {
          id: x.id, x: x.x, y: x.y, width: x.width, height: x.height,
          label: x.label, attrs: x.attrs,
        }
      }),
      edges: edges.map((e) => ({ id: e.id, source: e.source_id, target: e.target_id })),
    })
  }

  applyPositions(pos: Record<string, XYPos>): void {
    if (!this.graph) return
    for (const [id, p] of Object.entries(pos)) {
      this.graph.getCellById(id)?.isNode() && (this.graph.getCellById(id) as any).position(p.x, p.y)
    }
  }

  runLayout(): Record<string, XYPos> {
    const pos = dagre(this.nodes, this.edges)
    this.applyPositions(pos)
    return pos
  }

  highlightSelected(id: string | null): void {
    if (!this.graph) return
    this.graph.getNodes().forEach((node) => {
      node.attr("body/shadowBlur", node.id === id ? 12 : 0)
    })
  }

  applyMatch(ids: Set<string> | null): void {
    if (!this.graph) return
    this.graph.getNodes().forEach((node) => {
      const dim = ids !== null && !ids.has(node.id)
      node.attr("body/opacity", dim ? 0.25 : 1)
    })
  }

  centerOn(id: string): void {
    const cell = this.graph?.getCellById(id)
    if (cell?.isNode()) this.graph?.centerCell(cell)
  }

  getViewport(): { zoom: number; tx: number; ty: number } {
    const z = this.graph?.zoom() ?? 1
    const t = this.graph?.translate() ?? { tx: 0, ty: 0 }
    return { zoom: z, tx: t.tx, ty: t.ty }
  }

  setViewport(vp: { zoom: number; tx: number; ty: number }): void {
    this.graph?.zoomTo(vp.zoom)
    this.graph?.translate(vp.tx, vp.ty)
  }

  onNodeMoved(cb: (id: string, xy: XYPos) => void): void {
    this.graph?.on("node:moved", ({ node }) => {
      const p = node.position()
      cb(node.id, { x: p.x, y: p.y })
    })
  }

  onNodeClick(cb: (id: string) => void): void {
    this.graph?.on("node:click", ({ node }) => cb(node.id))
  }

  dispose(): void {
    this.graph?.dispose()
    this.graph = null
  }
}
```

> 若 @antv/x6 v3 的某 API（如 `centerCell`、`translate()` 返回形态、`fromJSON` label 字段）与此略有出入，实现时按 X6 v3 实际签名修正——保持上面"契约方法名 + 行为"不变（GraphCanvas 与测试只依赖这些方法名）。

- [ ] **Step 2: 创建 `frontend/src/components/graph/GraphCanvas.vue`**

```vue
<template>
  <div ref="el" class="x6-canvas" />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from "vue"
import type { Subgraph, XYPos } from "@/types/graph"
import { GraphController } from "./graphController"

const props = defineProps<{
  subgraph: Subgraph | null
  matchedIds: Set<string> | null
  selectedId: string | null
  savedPositions: Record<string, XYPos>
}>()
const emit = defineEmits<{ select: [id: string]; nodeMoved: [id: string, xy: XYPos] }>()

const el = ref<HTMLElement>()
const controller = new GraphController()

function render() {
  if (!props.subgraph) return
  controller.setData(props.subgraph.nodes, props.subgraph.edges)
  if (Object.keys(props.savedPositions).length > 0) controller.applyPositions(props.savedPositions)
  else controller.runLayout()
  controller.applyMatch(props.matchedIds)
  controller.highlightSelected(props.selectedId)
}

onMounted(() => {
  controller.init(el.value!)
  controller.onNodeClick((id) => emit("select", id))
  controller.onNodeMoved((id, xy) => emit("nodeMoved", id, xy))
  render()
})
onBeforeUnmount(() => controller.dispose())

watch(() => props.subgraph, render)
watch(() => props.matchedIds, (ids) => controller.applyMatch(ids))
watch(() => props.selectedId, (id) => controller.highlightSelected(id))

defineExpose({ relayout: () => controller.runLayout(), centerOn: (id: string) => controller.centerOn(id) })
</script>

<style scoped>
.x6-canvas { width: 100%; height: 100%; min-height: 70vh; }
</style>
```

- [ ] **Step 3: 写测试 `frontend/tests/GraphCanvas.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { mount } from "@vue/test-utils"

// mock 整个 graphController 模块，记录命令调用
const calls = vi.hoisted(() => ({
  init: vi.fn(), setData: vi.fn(), applyPositions: vi.fn(), runLayout: vi.fn(),
  highlightSelected: vi.fn(), applyMatch: vi.fn(), centerOn: vi.fn(),
  onNodeClick: vi.fn(), onNodeMoved: vi.fn(), dispose: vi.fn(),
}))
vi.mock("@/components/graph/graphController", () => ({
  GraphController: vi.fn(() => calls),
}))

import GraphCanvas from "@/components/graph/GraphCanvas.vue"

const SG = {
  nodes: [{ id: "a", name: "a", type: "t", priority: null, is_critical: false, parent_id: null }],
  edges: [], stats: { node_count: 1, edge_count: 0, has_cycle: false },
}

beforeEach(() => Object.values(calls).forEach((f) => f.mockReset()))

function mountCanvas(props = {}) {
  return mount(GraphCanvas, {
    props: { subgraph: SG, matchedIds: null, selectedId: null, savedPositions: {}, ...props },
    attachTo: document.body,
  })
}

it("挂载 init + setData，无持久位置时 runLayout", () => {
  mountCanvas()
  expect(calls.init).toHaveBeenCalled()
  expect(calls.setData).toHaveBeenCalled()
  expect(calls.runLayout).toHaveBeenCalled()
  expect(calls.applyPositions).not.toHaveBeenCalled()
})

it("有持久位置时 applyPositions 而非 runLayout", () => {
  mountCanvas({ savedPositions: { a: { x: 1, y: 2 } } })
  expect(calls.applyPositions).toHaveBeenCalledWith({ a: { x: 1, y: 2 } })
  expect(calls.runLayout).not.toHaveBeenCalled()
})

it("node:click 经回调 emit select", () => {
  const w = mountCanvas()
  // 取 onNodeClick 注册的回调并触发
  const cb = calls.onNodeClick.mock.calls[0][0] as (id: string) => void
  cb("a")
  expect(w.emitted("select")?.[0]).toEqual(["a"])
})

it("matchedIds 变化触发 applyMatch", async () => {
  const w = mountCanvas()
  calls.applyMatch.mockReset()
  await w.setProps({ matchedIds: new Set(["a"]) })
  expect(calls.applyMatch).toHaveBeenCalledWith(new Set(["a"]))
})

it("卸载 dispose", () => {
  const w = mountCanvas()
  w.unmount()
  expect(calls.dispose).toHaveBeenCalled()
})
```

- [ ] **Step 4: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -8`
Expected: 全绿（前两任务 + GraphCanvas 5）。

- [ ] **Step 5: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/components/graph/graphController.ts frontend/src/components/graph/GraphCanvas.vue frontend/tests/GraphCanvas.spec.ts
git commit -m "feat(frontend): F3a graphController（X6 封装）与 GraphCanvas 组件

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 4: 侧栏 + GraphView + 路由 + 构建

**Files:**
- Create: `frontend/src/components/sidebar/FilterBar.vue`, `frontend/src/components/sidebar/NodeTree.vue`, `frontend/src/views/GraphView.vue`
- Modify: `frontend/src/router/index.ts`
- Test: `frontend/tests/FilterBar.spec.ts`, `frontend/tests/NodeTree.spec.ts`, `frontend/tests/GraphView.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/components/sidebar/FilterBar.vue`**

```vue
<template>
  <div class="filter-bar">
    <el-input :model-value="filters.name" placeholder="搜索名称" clearable @update:model-value="(v) => set('name', v)" />
    <el-select :model-value="filters.type" placeholder="类型" clearable @update:model-value="(v) => set('type', v)">
      <el-option v-for="t in types" :key="t" :label="t" :value="t" />
    </el-select>
    <el-select :model-value="filters.priority" placeholder="优先级" clearable @update:model-value="(v) => set('priority', v)">
      <el-option v-for="p in priorities" :key="p" :label="p" :value="p" />
    </el-select>
    <el-input :model-value="filters.department" placeholder="部门" clearable @update:model-value="(v) => set('department', v)" />
    <el-input :model-value="filters.system" placeholder="系统" clearable @update:model-value="(v) => set('system', v)" />
    <el-input :model-value="filters.tag" placeholder="标签" clearable @update:model-value="(v) => set('tag', v)" />
    <el-button link @click="emit('clear')">清空</el-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import type { NodeFilters, NodeResponse } from "@/types/graph"

const props = defineProps<{ filters: NodeFilters; nodes: NodeResponse[] }>()
const emit = defineEmits<{ setFilter: [Partial<NodeFilters>]; clear: [] }>()

const priorities = ["P0", "P1", "P2", "P3", "P4", "P5"]
const types = computed(() => [...new Set(props.nodes.map((n) => n.type))])

function set(key: keyof NodeFilters, value: string) {
  emit("setFilter", { [key]: value || undefined })
}
</script>

<style scoped>
.filter-bar { display: flex; flex-direction: column; gap: 8px; }
</style>
```

- [ ] **Step 2: 创建 `frontend/src/components/sidebar/NodeTree.vue`**

```vue
<template>
  <el-tree
    :data="treeData"
    :props="{ label: 'label', children: 'children' }"
    node-key="id"
    @node-click="(d) => emit('select', d.id)"
  />
</template>

<script setup lang="ts">
import { computed } from "vue"
import type { NodeResponse } from "@/types/graph"

const props = defineProps<{ nodes: NodeResponse[]; matchedIds: Set<string> | null }>()
const emit = defineEmits<{ select: [id: string] }>()

interface TreeNode { id: string; label: string; children: TreeNode[] }

const treeData = computed<TreeNode[]>(() => {
  const visible = props.matchedIds
    ? props.nodes.filter((n) => props.matchedIds!.has(n.id))
    : props.nodes
  const byId = new Map<string, TreeNode>()
  for (const n of visible) {
    const tag = n.priority ? ` [${n.priority}]` : ""
    const star = n.is_critical ? " ★" : ""
    byId.set(n.id, { id: n.id, label: `${n.name}${tag}${star}`, children: [] })
  }
  const roots: TreeNode[] = []
  for (const n of visible) {
    const node = byId.get(n.id)!
    const parent = n.parent_id ? byId.get(n.parent_id) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  return roots
})
</script>
```

- [ ] **Step 3: 创建 `frontend/src/views/GraphView.vue`**

```vue
<template>
  <div class="graph-view">
    <aside class="sidebar">
      <FilterBar :filters="store.filters" :nodes="store.sidebarNodes" @set-filter="store.setFilter" @clear="store.clearFilters" />
      <el-divider />
      <NodeTree :nodes="store.sidebarNodes" :matched-ids="store.matchedIds" @select="onSelect" />
    </aside>
    <section class="canvas-area">
      <div class="toolbar">
        <span v-if="store.subgraph">节点 {{ store.subgraph.stats.node_count }} · 边 {{ store.subgraph.stats.edge_count }}<span v-if="store.subgraph.stats.has_cycle"> · ⚠ 有环</span></span>
        <el-button size="small" @click="onRelayout">重新布局</el-button>
      </div>
      <el-empty v-if="store.subgraph && store.subgraph.nodes.length === 0" description="暂无节点" />
      <GraphCanvas
        v-else
        ref="canvas"
        :subgraph="store.subgraph"
        :matched-ids="store.matchedIds"
        :selected-id="store.selectedId"
        :saved-positions="savedPositions"
        @select="onSelect"
        @node-moved="onNodeMoved"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { useGraphStore } from "@/stores/graph"
import { useAuthStore } from "@/stores/auth"
import { read, savePos, clear as clearPrefs } from "@/components/graph/viewPrefs"
import type { XYPos } from "@/types/graph"
import FilterBar from "@/components/sidebar/FilterBar.vue"
import NodeTree from "@/components/sidebar/NodeTree.vue"
import GraphCanvas from "@/components/graph/GraphCanvas.vue"

const route = useRoute()
const store = useGraphStore()
const auth = useAuthStore()
const pid = computed(() => Number(route.params.pid))
const uid = computed(() => auth.user?.id ?? 0)
const canvas = ref<InstanceType<typeof GraphCanvas>>()
const savedPositions = ref<Record<string, XYPos>>({})

onMounted(async () => {
  savedPositions.value = read(pid.value, uid.value).positions
  await store.loadGraph(pid.value)
})

function onSelect(id: string) {
  store.select(id)
  canvas.value?.centerOn(id)
}
function onNodeMoved(id: string, xy: XYPos) {
  savePos(pid.value, uid.value, id, xy)
}
function onRelayout() {
  clearPrefs(pid.value, uid.value)
  savedPositions.value = {}
  canvas.value?.relayout()
}
</script>

<style scoped>
.graph-view { display: flex; height: calc(100vh - 120px); }
.sidebar { width: 240px; padding: 12px; border-right: 1px solid #eee; overflow: auto; }
.canvas-area { flex: 1; display: flex; flex-direction: column; }
.toolbar { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid #eee; }
</style>
```

- [ ] **Step 4: 改 `frontend/src/router/index.ts`**

把 `/projects/:pid` children 里的 `{ path: "", redirect: (to) => ... }` 替换为：
```ts
      { path: "", name: "graph", component: () => import("@/views/GraphView.vue") },
```
（members/schemas 子路由保持不变。ProjectLayout 侧导航加一条"图谱"链接指向 `/projects/${pid}`——若 ProjectLayout 已渲染 `<router-link :to="/projects/${pid}/members">` 等，追加 `<router-link :to="/projects/${pid}">图谱</router-link>` 在最前。）

- [ ] **Step 5: 在 `frontend/src/views/ProjectLayout.vue` 侧导航加图谱链接**

在 `<nav class="side">` 内、成员链接之前加：
```html
        <router-link :to="`/projects/${pid}`">图谱</router-link>
```

- [ ] **Step 6: 写测试 `frontend/tests/FilterBar.spec.ts`**

```ts
import { it, expect, vi } from "vitest"
import { mount } from "@vue/test-utils"
import ElementPlus from "element-plus"
import FilterBar from "@/components/sidebar/FilterBar.vue"

const NODES = [
  { id: "a", project_id: 1, name: "a", type: "data_task", description: null, owner: null, department: null, system: null, priority: null, tags: [], ext_props: {}, is_critical: false, parent_id: null, children_count: 0, upstream_count: 0, downstream_count: 0 },
  { id: "b", project_id: 1, name: "b", type: "service", description: null, owner: null, department: null, system: null, priority: null, tags: [], ext_props: {}, is_critical: false, parent_id: null, children_count: 0, upstream_count: 0, downstream_count: 0 },
]

function mountBar() {
  return mount(FilterBar, { props: { filters: {}, nodes: NODES }, global: { plugins: [ElementPlus] } })
}

it("name 输入 emit setFilter", async () => {
  const w = mountBar()
  await w.find("input").setValue("alpha")
  const e = w.emitted("setFilter")
  expect(e).toBeTruthy()
  expect(e![e!.length - 1][0]).toEqual({ name: "alpha" })
})

it("清空 emit clear", async () => {
  const w = mountBar()
  await w.findAll("button").find((b) => b.text() === "清空")!.trigger("click")
  expect(w.emitted("clear")).toBeTruthy()
})
```

- [ ] **Step 7: 写测试 `frontend/tests/NodeTree.spec.ts`**

```ts
import { it, expect, vi } from "vitest"
import { mount } from "@vue/test-utils"
import ElementPlus from "element-plus"
import NodeTree from "@/components/sidebar/NodeTree.vue"

const N = (id: string, parent: string | null = null) => ({
  id, project_id: 1, name: id, type: "t", description: null, owner: null, department: null,
  system: null, priority: null, tags: [], ext_props: {}, is_critical: false,
  parent_id: parent, children_count: 0, upstream_count: 0, downstream_count: 0,
})

function mountTree(props: Record<string, unknown>) {
  return mount(NodeTree, { props: { matchedIds: null, ...props }, global: { plugins: [ElementPlus] } })
}

it("渲染父子层级", () => {
  const w = mountTree({ nodes: [N("root"), N("child", "root")] })
  expect(w.text()).toContain("root")
  expect(w.text()).toContain("child")
})

it("matchedIds 过滤只显示匹配", () => {
  const w = mountTree({ nodes: [N("a"), N("b")], matchedIds: new Set(["a"]) })
  expect(w.text()).toContain("a")
  expect(w.text()).not.toContain("b")
})

it("点击节点 emit select", async () => {
  const w = mountTree({ nodes: [N("a")] })
  await w.find(".el-tree-node__content").trigger("click")
  expect(w.emitted("select")?.[0]).toEqual(["a"])
})
```

- [ ] **Step 8: 写测试 `frontend/tests/GraphView.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"

const store = vi.hoisted(() => ({
  subgraph: { nodes: [{ id: "a", name: "a", type: "t", priority: null, is_critical: false, parent_id: null }], edges: [], stats: { node_count: 1, edge_count: 0, has_cycle: false } },
  sidebarNodes: [], selectedId: null, filters: {}, matchedIds: null,
  loadGraph: vi.fn(), select: vi.fn(), setFilter: vi.fn(), clearFilters: vi.fn(),
}))
vi.mock("@/stores/graph", () => ({ useGraphStore: () => store }))
vi.mock("@/stores/auth", () => ({ useAuthStore: () => ({ user: { id: 7 } }) }))
vi.mock("vue-router", () => ({ useRoute: () => ({ params: { pid: "1" } }) }))
// stub 重组件
vi.mock("@/components/graph/GraphCanvas.vue", () => ({ default: { name: "GraphCanvas", template: "<div class='gc' />" } }))
vi.mock("@/components/sidebar/FilterBar.vue", () => ({ default: { name: "FilterBar", template: "<div class='fb' />" } }))
vi.mock("@/components/sidebar/NodeTree.vue", () => ({ default: { name: "NodeTree", template: "<div class='nt' />" } }))
import ElementPlus from "element-plus"
import GraphView from "@/views/GraphView.vue"

beforeEach(() => { store.loadGraph.mockReset() })

it("onMounted 调 loadGraph(pid) 并渲染 canvas+侧栏", async () => {
  const w = mount(GraphView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(store.loadGraph).toHaveBeenCalledWith(1)
  expect(w.find(".gc").exists()).toBe(true)
  expect(w.find(".fb").exists()).toBe(true)
  expect(w.find(".nt").exists()).toBe(true)
})
```

- [ ] **Step 9: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -10`
Expected: 全绿。若 el-tree 的 `.el-tree-node__content` 选择器或 node-click 行为不符，调整 NodeTree 测试 accessor（不弱化"点击 emit select(id)"与"matchedIds 过滤"断言）。

- [ ] **Step 10: 类型检查 + 构建（F3a DoD 闸门）**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run build 2>&1 | tail -12`
Expected: vue-tsc 无类型错误（含 @antv/x6、@antv/layout 类型），vite build 产出 dist/。按报错精确修，不放宽 strict。X6/layout 若有类型导出问题，必要时在该文件局部 `// @ts-expect-error` 注释具体行并说明（仅限第三方类型缺陷，不用于自有代码）。

- [ ] **Step 11: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/components/sidebar/FilterBar.vue frontend/src/components/sidebar/NodeTree.vue frontend/src/views/GraphView.vue frontend/src/router/index.ts frontend/src/views/ProjectLayout.vue frontend/tests/FilterBar.spec.ts frontend/tests/NodeTree.spec.ts frontend/tests/GraphView.spec.ts
git commit -m "feat(frontend): F3a 侧栏过滤/树、GraphView 主视图与画布路由

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Phase F3a 完成标准（Definition of Done）

- [ ] `npm run build`（vue-tsc）通过、无 TS 错误（含 @antv/x6、@antv/layout）。
- [ ] `npm run test` 全绿（F1+F2 既有 39 + F3a 新增）。
- [ ] 手动：进项目 → 画布渲染全图（dagre、type 着色、is_critical 高亮、priority 标签）→ 平移/缩放/选中 → 侧栏树点击居中 → FilterBar 过滤画布高亮/置灰 → 手拖节点刷新后位置保留 → "重新布局"重排并清持久位置。
- [ ] 画布是 `/projects/:pid` 主视图；空图显示空状态；ProjectLayout 侧栏有"图谱"链接。

## 下一子项目预告（不在本计划内）

- F3b：画布变更（建节点 name+type、连线建边、拖入建父子、删节点/边）——复用 controller/store。
- F4：属性面板 + 影响分析着色。F5：SQL/文件导入入口。




