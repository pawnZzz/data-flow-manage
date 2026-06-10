# 任务血缘工具 前端 F2：项目 + 成员 + Schema 管理 — 设计文档

**日期：** 2026-06-09
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§5.2/5.3 项目·成员·schema API、§7 前端结构）
**前置：** 前端 F1（脚手架+认证+API基座，已完成）；后端 Phase 1-3 全部完成。

## 背景

前端拆为 F1-F5。F1 建好地基（client/store/router/守卫）。**F2** 加三块管理 UI：项目列表、成员管理、Schema 管理。复用 F1 的 `http` client、auth store、路由守卫。

## 目标

在 F1 之上加项目/成员/Schema 三块 CRUD 管理界面，建立项目选择 → 进入项目 → 管理成员/类型 schema 的完整流程。

## 范围

**做：**
- 项目列表 `/projects`：列我的项目（my_role+status）、建项目、归档/恢复/purge、显示归档过滤、进入项目。
- ProjectLayout `/projects/:pid`：壳（顶栏 + 侧导航 + 子路由出口）；本期 `/projects/:pid` → 重定向 `/projects/:pid/members`（F3 改画布）。
- 成员 `/projects/:pid/members`：列/加/改角色/移除（admin+ 写）。
- Schema `/projects/:pid/schemas`：列/建/改/删（含 SchemaForm 动态字段编辑器；editor 建改、admin 删）。

**不做（留 F3+）：** 画布、节点/边、影响分析、SQL/文件导入、审计页。

## 决策（已与用户确认）

- **子页结构**：ProjectLayout 壳 + 子路由（/members、/schemas），与 master §7.1 一致；F3 画布主视图后续插入同壳。
- **RBAC 按钮**：权限不足的写操作按钮 `v-if` 按 `my_role` 隐藏（后端仍是唯一权威）。
- **purge 确认**：输入项目名确认（ElMessageBox.prompt，输入须 == project.name）。
- **范围**：项目列表 + 成员 + Schema 三块本期一起做。
- **`/` 重定向**：F1 的 `/profile` 改为 `/projects`。

## 后端契约（对齐，全在 /api/v1）

| 资源 | 端点 | 权限 |
|------|------|------|
| 项目 | GET `/projects?include_archived=` → Project[]（含 my_role） | 成员 |
| | POST `/projects` {name,description?} → Project | 登录用户 |
| | GET `/projects/:pid` → Project | viewer |
| | PATCH `/projects/:pid` {name?,description?} | admin |
| | DELETE `/projects/:pid`（归档） | owner |
| | POST `/projects/:pid/unarchive` → Project | owner |
| | POST `/projects/:pid/purge` → {deleted_nodes,deleted_schemas} | owner |
| 成员 | GET `/projects/:pid/members` → Member[] | viewer |
| | POST `/projects/:pid/members` {username?\|email?,role} → Member | admin |
| | PATCH `/projects/:pid/members/:uid` {role} → Member | admin |
| | DELETE `/projects/:pid/members/:uid` | admin |
| schema | GET `/projects/:pid/schemas` → Schema[] | viewer |
| | POST `/projects/:pid/schemas` {type_key,display_name,fields} | editor |
| | PUT `/projects/:pid/schemas/:type_key` {display_name?,fields?} | editor |
| | DELETE `/projects/:pid/schemas/:type_key`（占用 409） | admin |

`Project={id,name,description,status,created_by,my_role}`；`Member={user_id,username,display_name,role}`；`SchemaField={name,label,type:string\|number\|url\|enum\|bool,required,options?,default?}`；`Schema={id,type_key,display_name,fields,created_at,updated_at}`。role ∈ owner/admin/editor/viewer。

## 1. 文件结构

```
src/
├── api/
│   ├── projects.ts   # list/create/get/update/archive/unarchive/purge
│   ├── members.ts    # list/add/changeRole/remove
│   └── schemas.ts    # list/create/get/update/remove
├── stores/
│   └── project.ts    # current project + my_role + can(role) RBAC 工具
├── views/
│   ├── ProjectListView.vue
│   ├── ProjectLayout.vue        # 壳：顶栏 + 侧导航 + <router-view>
│   ├── MembersView.vue
│   └── SchemasView.vue
├── components/
│   ├── ProjectFormDialog.vue    # 建/改项目
│   ├── MemberFormDialog.vue     # 加成员
│   └── SchemaForm.vue           # schema 字段动态编辑（建/改复用）
├── types/graph.ts               # Project/Member/Schema/SchemaField/Role 类型
└── router/index.ts              # 改：加 /projects + /projects/:pid 壳与子路由；/ → /projects
```

## 2. 类型 `types/graph.ts`

```ts
export type Role = "owner" | "admin" | "editor" | "viewer"
export interface Project { id: number; name: string; description: string | null; status: string; created_by: number; my_role: Role }
export interface Member { user_id: number; username: string; display_name: string | null; role: Role }
export type FieldType = "string" | "number" | "url" | "enum" | "bool"
export interface SchemaField { name: string; label: string; type: FieldType; required: boolean; options?: string[] | null; default?: unknown }
export interface NodeTypeSchema { id: string; type_key: string; display_name: string; fields: SchemaField[]; created_at: string; updated_at: string }
export interface PurgeResult { deleted_nodes: number; deleted_schemas: number }
```

## 3. API 模块（经 F1 `http`）

```ts
// projects.ts
listProjects(includeArchived = false): Promise<Project[]>   // GET /projects?include_archived=
createProject(body: { name: string; description?: string | null }): Promise<Project>
getProject(pid: number): Promise<Project>
updateProject(pid, body: { name?: string; description?: string | null }): Promise<Project>
archiveProject(pid): Promise<void>                          // DELETE /projects/:pid
unarchiveProject(pid): Promise<Project>
purgeProject(pid): Promise<PurgeResult>
// members.ts
listMembers(pid): Promise<Member[]>
addMember(pid, body: { username?: string; email?: string; role: Role }): Promise<Member>
changeRole(pid, uid, role: Role): Promise<Member>
removeMember(pid, uid): Promise<void>
// schemas.ts
listSchemas(pid): Promise<NodeTypeSchema[]>
createSchema(pid, body: { type_key: string; display_name: string; fields: SchemaField[] }): Promise<NodeTypeSchema>
updateSchema(pid, typeKey, body: { display_name?: string; fields?: SchemaField[] }): Promise<NodeTypeSchema>
removeSchema(pid, typeKey): Promise<void>
```

## 4. `stores/project.ts`（Pinia setup store）

- state：`current = ref<Project | null>(null)`。
- getter：`myRole = computed(() => current.value?.my_role ?? null)`。
- 工具 `can(min: Role): boolean`：角色等级 `{owner:4, admin:3, editor:2, viewer:1}`，`current` 存在且 `level[myRole] >= level[min]`。
- actions：`load(pid)`（`getProject` → current）、`clear()`。
- ProjectLayout 在 `onMounted` 与 `watch(() => route.params.pid)` 调 `load`；视图/按钮用 `projectStore.can("admin")` 等显隐。

## 5. 视图行为

**ProjectListView** `/projects`：
- `listProjects(includeArchived)`；`el-switch` 切「显示归档」重拉。
- 顶部「新建项目」（登录用户皆可）→ ProjectFormDialog → `createProject` → 刷新。
- 行操作按 `row.my_role`（每行自带）：进入（全员，跳 `/projects/:id`）、改名（admin，ProjectFormDialog edit）、归档（owner，`ElMessageBox.confirm`）；归档状态行显示恢复（owner，`unarchiveProject`）、永久删除（owner，**输项目名确认**：`ElMessageBox.prompt`，输入 trim 后须 === row.name，否则不调用；成功 `ElMessage.success("已删除 N 节点/M schema")` + 刷新）。

**ProjectLayout** `/projects/:pid`：
- `onMounted`/`watch pid` → `projectStore.load(pid)`；load 失败（拦截器已处理 403/404 跳转/提示）兜底 `router.replace("/projects")`。
- 顶栏：项目名 + status 标签；侧导航：成员、Schema（F3 加画布）；`<router-view>`。

**MembersView** `/projects/:pid/members`：
- `listMembers`；`projectStore.can("admin")` 才显示「加成员」「改角色」「移除」。
- 加成员 MemberFormDialog（username 或 email 二选一 + role 下拉）→ `addMember` → 刷新。
- 改角色：行内 `el-select` 或对话框 → `changeRole`。移除：`confirm` → `removeMember`。
- owner 行不显示改/移按钮（前端据 row.role==="owner" 隐藏；后端亦挡）。

**SchemasView** `/projects/:pid/schemas`：
- `listSchemas`；`can("editor")` 显「新建/编辑」、`can("admin")` 显「删除」。
- 新建/编辑 → SchemaForm 对话框 → `createSchema`/`updateSchema` → 刷新。
- 删除 `confirm` → `removeSchema`（占用时后端 409，拦截器弹消息）。

## 6. `components/SchemaForm.vue`（最复杂件）

- props：`modelValue: {type_key, display_name, fields}`、`isEdit: boolean`（改时 type_key 只读/disabled）。emit `submit` 携规范化 payload。
- 表单：type_key（建可填、改 disabled）、display_name。
- **字段动态列表**：每行 `name` / `label` / `type`(下拉 string|number|url|enum|bool) / `required`(switch) / `default`(可选输入) + 删除按钮；底部「添加字段」追加空行。
- `type === "enum"` 时该行显示 `options` 编辑（逗号分隔输入，提交时 split/trim 成数组）；非 enum 隐藏 options。
- 校验：type_key（建时）/display_name 非空；每个字段 name 非空且行内唯一；enum 字段 options ≥1。校验不过 `ElMessage.warning` 并阻止提交。
- 提交：emit `{type_key, display_name, fields}`，每个 field 规范化（非 enum 的 `options` 置 null）。

## 7. RBAC 工具

`projectStore.can(min: Role)` 角色等级映射 `{owner:4, admin:3, editor:2, viewer:1}` 比较，集中一处。视图按钮 `v-if="projectStore.can('admin')"`；列表行用 `row.my_role` 自带等级判断（同一映射，抽一个 `roleAtLeast(role, min)` 纯函数复用）。

## 8. 测试（Vitest + @vue/test-utils，mock api 层）

- `project.store.spec.ts`：load 填 current；`can()` 边界（viewer 不可 admin、admin 可 editor、owner 可 owner、无 current 全 false）。
- `ProjectListView.spec.ts`：渲染列表；建项目调 createProject；归档调 archiveProject；「显示归档」切换重拉 listProjects(true)；purge 输错名不调用、输对名调 purgeProject。
- `MembersView.spec.ts`：渲染成员；`can('admin')` 时显加成员按钮、viewer 不显；加成员调 addMember；移除调 removeMember；owner 行不显示移除。
- `SchemasView.spec.ts`：渲染 schema 列表；`can('editor')` 显新建；建 schema 调 createSchema。
- `SchemaForm.spec.ts`：加/删字段行；选 enum 显 options、非 enum 不显；缺 name / 空 options 校验拦截提交；提交 emit 规范化 payload（非 enum options=null）。
- `ProjectLayout.spec.ts`：mount 调 projectStore.load(pid)；渲染侧导航链接。

## Definition of Done

- `npm run build`（vue-tsc 类型检查）通过、无 TS 错误。
- `npm run test` 全绿（F1 既有 19 + F2 新增）。
- 手动：起后端 + dev，登录 → 项目列表建项目 → 进入项目 → 加成员/改角色/移除 → 建/改/删 schema（含 enum 字段）→ 归档/恢复/purge（输名确认）全流程走通。
- RBAC：viewer 身份看不到写按钮；越权时后端 403/409 被拦截器提示。
- `/` 重定向到 `/projects`；未登录被守卫挡到 /login。

## 下一子项目预告（不在本计划内）

- F3：画布核心（X6）——ProjectLayout 加 `/projects/:pid` 画布主视图，GraphCanvas + 节点/边交互 + 侧栏过滤。
- F4：属性面板 + 影响分析可视化。F5：SQL/文件导入入口。


