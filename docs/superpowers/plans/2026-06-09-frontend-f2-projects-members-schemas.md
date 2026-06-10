# 前端 F2：项目 + 成员 + Schema 管理 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在前端 F1 之上加项目列表、成员管理、Schema 管理三块 CRUD UI（含 ProjectLayout 壳、RBAC 按钮显隐、purge 输名确认、SchemaForm 动态字段编辑器）。

**Architecture:** 分层 api(http 封装) → stores/project(当前项目+RBAC) → views/components。复用 F1 的 `http` client、auth store、路由守卫。RBAC 用 `roleAtLeast` 纯函数集中判定。

**Tech Stack:** Vue 3(`<script setup>`+TS)、Pinia、Vue Router、Element Plus、Vitest、@vue/test-utils。

参考 spec：`docs/superpowers/specs/2026-06-09-frontend-f2-projects-members-schemas-design.md`。

---

## File Structure

- `frontend/src/types/graph.ts` — Role/Project/Member/SchemaField/NodeTypeSchema/PurgeResult 类型 + `roleAtLeast`。
- `frontend/src/api/projects.ts`、`members.ts`、`schemas.ts` — 端点封装。
- `frontend/src/stores/project.ts` — current project + `can(role)`。
- `frontend/src/views/ProjectListView.vue`、`ProjectLayout.vue`、`MembersView.vue`、`SchemasView.vue`。
- `frontend/src/components/ProjectFormDialog.vue`、`MemberFormDialog.vue`、`SchemaForm.vue`。
- `frontend/src/router/index.ts` — 改：加 /projects、/projects/:pid 壳 + 子路由；/ → /projects。
- 测试：`frontend/tests/` 下 project.store / ProjectListView / MembersView / SchemasView / SchemaForm / ProjectLayout 各 .spec.ts。

约定：命令在 `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend` 下跑；commit 在仓库根；message 末尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。`@` 别名 → src。

## Task 1: 类型 + API 模块 + project store

**Files:**
- Create: `frontend/src/types/graph.ts`, `frontend/src/api/projects.ts`, `frontend/src/api/members.ts`, `frontend/src/api/schemas.ts`, `frontend/src/stores/project.ts`
- Test: `frontend/tests/project.store.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/types/graph.ts`**

```ts
export type Role = "owner" | "admin" | "editor" | "viewer"

const ROLE_LEVEL: Record<Role, number> = { owner: 4, admin: 3, editor: 2, viewer: 1 }

export function roleAtLeast(role: Role | null | undefined, min: Role): boolean {
  if (!role) return false
  return ROLE_LEVEL[role] >= ROLE_LEVEL[min]
}

export interface Project {
  id: number
  name: string
  description: string | null
  status: string
  created_by: number
  my_role: Role
}

export interface Member {
  user_id: number
  username: string
  display_name: string | null
  role: Role
}

export type FieldType = "string" | "number" | "url" | "enum" | "bool"

export interface SchemaField {
  name: string
  label: string
  type: FieldType
  required: boolean
  options?: string[] | null
  default?: unknown
}

export interface NodeTypeSchema {
  id: string
  type_key: string
  display_name: string
  fields: SchemaField[]
  created_at: string
  updated_at: string
}

export interface PurgeResult {
  deleted_nodes: number
  deleted_schemas: number
}
```

- [ ] **Step 2: 创建 `frontend/src/api/projects.ts`**

```ts
import { http } from "./client"
import type { Project, PurgeResult } from "@/types/graph"

export const projectsApi = {
  list: (includeArchived = false) =>
    http.get("/projects", { params: { include_archived: includeArchived } }) as unknown as Promise<Project[]>,
  create: (body: { name: string; description?: string | null }) =>
    http.post("/projects", body) as unknown as Promise<Project>,
  get: (pid: number) => http.get(`/projects/${pid}`) as unknown as Promise<Project>,
  update: (pid: number, body: { name?: string; description?: string | null }) =>
    http.patch(`/projects/${pid}`, body) as unknown as Promise<Project>,
  archive: (pid: number) => http.delete(`/projects/${pid}`) as unknown as Promise<void>,
  unarchive: (pid: number) => http.post(`/projects/${pid}/unarchive`) as unknown as Promise<Project>,
  purge: (pid: number) => http.post(`/projects/${pid}/purge`) as unknown as Promise<PurgeResult>,
}
```

- [ ] **Step 3: 创建 `frontend/src/api/members.ts`**

```ts
import { http } from "./client"
import type { Member, Role } from "@/types/graph"

export const membersApi = {
  list: (pid: number) => http.get(`/projects/${pid}/members`) as unknown as Promise<Member[]>,
  add: (pid: number, body: { username?: string; email?: string; role: Role }) =>
    http.post(`/projects/${pid}/members`, body) as unknown as Promise<Member>,
  changeRole: (pid: number, uid: number, role: Role) =>
    http.patch(`/projects/${pid}/members/${uid}`, { role }) as unknown as Promise<Member>,
  remove: (pid: number, uid: number) =>
    http.delete(`/projects/${pid}/members/${uid}`) as unknown as Promise<void>,
}
```

- [ ] **Step 4: 创建 `frontend/src/api/schemas.ts`**

```ts
import { http } from "./client"
import type { NodeTypeSchema, SchemaField } from "@/types/graph"

export const schemasApi = {
  list: (pid: number) => http.get(`/projects/${pid}/schemas`) as unknown as Promise<NodeTypeSchema[]>,
  create: (pid: number, body: { type_key: string; display_name: string; fields: SchemaField[] }) =>
    http.post(`/projects/${pid}/schemas`, body) as unknown as Promise<NodeTypeSchema>,
  update: (pid: number, typeKey: string, body: { display_name?: string; fields?: SchemaField[] }) =>
    http.put(`/projects/${pid}/schemas/${typeKey}`, body) as unknown as Promise<NodeTypeSchema>,
  remove: (pid: number, typeKey: string) =>
    http.delete(`/projects/${pid}/schemas/${typeKey}`) as unknown as Promise<void>,
}
```

- [ ] **Step 5: 创建 `frontend/src/stores/project.ts`**

```ts
import { computed, ref } from "vue"
import { defineStore } from "pinia"
import { projectsApi } from "@/api/projects"
import { roleAtLeast, type Project, type Role } from "@/types/graph"

export const useProjectStore = defineStore("project", () => {
  const current = ref<Project | null>(null)

  const myRole = computed<Role | null>(() => current.value?.my_role ?? null)

  function can(min: Role): boolean {
    return roleAtLeast(myRole.value, min)
  }

  async function load(pid: number) {
    current.value = await projectsApi.get(pid)
  }

  function clear() {
    current.value = null
  }

  return { current, myRole, can, load, clear }
})
```

- [ ] **Step 6: 写测试 `frontend/tests/project.store.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"
import { roleAtLeast } from "@/types/graph"

const api = { get: vi.fn() }
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
```

- [ ] **Step 7: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -8`
Expected: 全绿（F1 既有 19 + 本任务 4 = 23）。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/types/graph.ts frontend/src/api/projects.ts frontend/src/api/members.ts frontend/src/api/schemas.ts frontend/src/stores/project.ts frontend/tests/project.store.spec.ts
git commit -m "feat(frontend): F2 项目/成员/schema API 模块、类型与 project store

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 2: 项目列表 + 建/改对话框 + 路由接线

**Files:**
- Create: `frontend/src/components/ProjectFormDialog.vue`, `frontend/src/views/ProjectListView.vue`
- Modify: `frontend/src/router/index.ts`
- Test: `frontend/tests/ProjectListView.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/components/ProjectFormDialog.vue`**

```vue
<template>
  <el-dialog :model-value="visible" :title="isEdit ? '编辑项目' : '新建项目'" @update:model-value="emit('close')">
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent>
      <el-form-item prop="name" label="名称">
        <el-input v-model="form.name" placeholder="项目名称" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :loading="busy" @click="onSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from "vue"
import { type FormInstance, type FormRules } from "element-plus"
import type { Project } from "@/types/graph"

const props = defineProps<{ visible: boolean; isEdit: boolean; project?: Project | null }>()
const emit = defineEmits<{ close: []; submit: [{ name: string; description: string | null }] }>()

const formRef = ref<FormInstance>()
const form = reactive({ name: "", description: "" })
const busy = ref(false)
const rules: FormRules = { name: [{ required: true, message: "请输入名称", trigger: "blur" }] }

watch(
  () => props.visible,
  (v) => {
    if (v) {
      form.name = props.project?.name ?? ""
      form.description = props.project?.description ?? ""
    }
  },
)

async function onSubmit() {
  if (!(await formRef.value?.validate().catch(() => false))) return
  busy.value = true
  try {
    emit("submit", { name: form.name, description: form.description || null })
  } finally {
    busy.value = false
  }
}
</script>
```

- [ ] **Step 2: 创建 `frontend/src/views/ProjectListView.vue`**

```vue
<template>
  <div class="list-wrap">
    <div class="bar">
      <h2>我的项目</h2>
      <div>
        <el-switch v-model="showArchived" active-text="显示归档" @change="reload" />
        <el-button type="primary" @click="openCreate">新建项目</el-button>
      </div>
    </div>
    <el-table :data="projects" v-loading="loading">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="my_role" label="我的角色" width="100" />
      <el-table-column label="操作" width="320">
        <template #default="{ row }">
          <el-button link type="primary" @click="enter(row)">进入</el-button>
          <el-button v-if="roleAtLeast(row.my_role, 'admin')" link @click="openEdit(row)">改名</el-button>
          <el-button v-if="row.status === 'active' && roleAtLeast(row.my_role, 'owner')" link type="warning" @click="onArchive(row)">归档</el-button>
          <el-button v-if="row.status === 'archived' && roleAtLeast(row.my_role, 'owner')" link @click="onUnarchive(row)">恢复</el-button>
          <el-button v-if="row.status === 'archived' && roleAtLeast(row.my_role, 'owner')" link type="danger" @click="onPurge(row)">永久删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <ProjectFormDialog
      :visible="dialogVisible" :is-edit="editing !== null" :project="editing"
      @close="dialogVisible = false" @submit="onDialogSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { projectsApi } from "@/api/projects"
import { roleAtLeast, type Project } from "@/types/graph"
import ProjectFormDialog from "@/components/ProjectFormDialog.vue"

const router = useRouter()
const projects = ref<Project[]>([])
const loading = ref(false)
const showArchived = ref(false)
const dialogVisible = ref(false)
const editing = ref<Project | null>(null)

async function reload() {
  loading.value = true
  try {
    projects.value = await projectsApi.list(showArchived.value)
  } finally {
    loading.value = false
  }
}
onMounted(reload)

function enter(row: Project) {
  router.push(`/projects/${row.id}`)
}
function openCreate() {
  editing.value = null
  dialogVisible.value = true
}
function openEdit(row: Project) {
  editing.value = row
  dialogVisible.value = true
}
async function onDialogSubmit(body: { name: string; description: string | null }) {
  if (editing.value) await projectsApi.update(editing.value.id, body)
  else await projectsApi.create(body)
  dialogVisible.value = false
  ElMessage.success("已保存")
  await reload()
}
async function onArchive(row: Project) {
  await ElMessageBox.confirm(`归档项目「${row.name}」？归档后不可写。`, "确认", { type: "warning" })
  await projectsApi.archive(row.id)
  ElMessage.success("已归档")
  await reload()
}
async function onUnarchive(row: Project) {
  await projectsApi.unarchive(row.id)
  ElMessage.success("已恢复")
  await reload()
}
async function onPurge(row: Project) {
  const { value } = await ElMessageBox.prompt(
    `永久删除「${row.name}」不可恢复。请输入项目名以确认：`, "危险操作",
    { type: "error", inputValidator: (v) => v?.trim() === row.name || "名称不匹配" },
  )
  if (value?.trim() !== row.name) return
  const res = await projectsApi.purge(row.id)
  ElMessage.success(`已删除：${res.deleted_nodes} 节点 / ${res.deleted_schemas} schema`)
  await reload()
}
</script>

<style scoped>
.list-wrap { max-width: 960px; margin: 32px auto; }
.bar { display: flex; justify-content: space-between; align-items: center; }
</style>
```

- [ ] **Step 3: 改 `frontend/src/router/index.ts`**

把 routes 数组中的 `{ path: "/", redirect: "/profile" }` 改为 `{ path: "/", redirect: "/projects" }`，并在 `/profile` 路由后追加：
```ts
  { path: "/projects", name: "projects", component: () => import("@/views/ProjectListView.vue") },
```
（ProjectLayout 与子路由在 Task 3 加。本任务先让 /projects 可达。）

- [ ] **Step 4: 写测试 `frontend/tests/ProjectListView.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"

const api = {
  list: vi.fn(), create: vi.fn(), update: vi.fn(),
  archive: vi.fn(), unarchive: vi.fn(), purge: vi.fn(),
}
vi.mock("@/api/projects", () => ({ projectsApi: api }))
const push = vi.fn()
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }))
const confirm = vi.fn()
const prompt = vi.fn()
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { success: vi.fn(), error: vi.fn() }, ElMessageBox: { confirm: (...a: unknown[]) => confirm(...a), prompt: (...a: unknown[]) => prompt(...a) } }
})

import ProjectListView from "@/views/ProjectListView.vue"

const ACTIVE = { id: 1, name: "Alpha", description: null, status: "active", created_by: 1, my_role: "owner" }
const ARCHIVED = { id: 2, name: "Beta", description: null, status: "archived", created_by: 1, my_role: "owner" }

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  push.mockReset(); confirm.mockReset(); prompt.mockReset()
  api.list.mockResolvedValue([ACTIVE])
})

async function mountView() {
  const w = mount(ProjectListView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

it("挂载即拉取项目列表", async () => {
  const w = await mountView()
  expect(api.list).toHaveBeenCalledWith(false)
  expect(w.text()).toContain("Alpha")
})

it("显示归档切换重拉 list(true)", async () => {
  const w = await mountView()
  await w.findComponent({ name: "ElSwitch" }).find("input").setValue(true)
  await flushPromises()
  expect(api.list).toHaveBeenCalledWith(true)
})

it("purge 输错名不调用 purge", async () => {
  api.list.mockResolvedValue([ARCHIVED])
  prompt.mockResolvedValue({ value: "WRONG" })
  const w = await mountView()
  await w.findAll("button").find((b) => b.text() === "永久删除")!.trigger("click")
  await flushPromises()
  expect(api.purge).not.toHaveBeenCalled()
})

it("purge 输对名调用 purge", async () => {
  api.list.mockResolvedValue([ARCHIVED])
  prompt.mockResolvedValue({ value: "Beta" })
  api.purge.mockResolvedValue({ deleted_nodes: 0, deleted_schemas: 0 })
  const w = await mountView()
  await w.findAll("button").find((b) => b.text() === "永久删除")!.trigger("click")
  await flushPromises()
  expect(api.purge).toHaveBeenCalledWith(2)
})
```

- [ ] **Step 5: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -8`
Expected: 全绿（23 + 本任务 4 = 27）。若 ElSwitch 选择器或 prompt mock 行为与实际不符，调整测试机制（不弱化"输对名才 purge"断言）。

- [ ] **Step 6: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/components/ProjectFormDialog.vue frontend/src/views/ProjectListView.vue frontend/src/router/index.ts frontend/tests/ProjectListView.spec.ts
git commit -m "feat(frontend): F2 项目列表（建/归档/恢复/purge 输名确认）与路由

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 3: ProjectLayout 壳 + 成员管理 + 子路由

**Files:**
- Create: `frontend/src/views/ProjectLayout.vue`, `frontend/src/views/MembersView.vue`, `frontend/src/components/MemberFormDialog.vue`
- Modify: `frontend/src/router/index.ts`
- Test: `frontend/tests/ProjectLayout.spec.ts`, `frontend/tests/MembersView.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/views/ProjectLayout.vue`**

```vue
<template>
  <div class="layout" v-if="proj.current">
    <header class="topbar">
      <span class="name">{{ proj.current.name }}</span>
      <el-tag size="small">{{ proj.current.status }}</el-tag>
      <el-button class="back" link @click="router.push('/projects')">← 项目列表</el-button>
    </header>
    <div class="body">
      <nav class="side">
        <router-link :to="`/projects/${pid}/members`">成员</router-link>
        <router-link :to="`/projects/${pid}/schemas`">类型 Schema</router-link>
      </nav>
      <main class="content"><router-view /></main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useProjectStore } from "@/stores/project"

const route = useRoute()
const router = useRouter()
const proj = useProjectStore()
const pid = computed(() => Number(route.params.pid))

async function loadProject(id: number) {
  try {
    await proj.load(id)
  } catch {
    router.replace("/projects")
  }
}

watch(pid, (id) => { if (id) loadProject(id) }, { immediate: true })
</script>

<style scoped>
.topbar { display: flex; align-items: center; gap: 12px; padding: 12px 20px; border-bottom: 1px solid #eee; }
.name { font-weight: 600; font-size: 16px; }
.back { margin-left: auto; }
.body { display: flex; }
.side { width: 160px; display: flex; flex-direction: column; padding: 16px; gap: 8px; border-right: 1px solid #eee; min-height: 70vh; }
.content { flex: 1; padding: 20px; }
</style>
```

- [ ] **Step 2: 创建 `frontend/src/components/MemberFormDialog.vue`**

```vue
<template>
  <el-dialog :model-value="visible" title="添加成员" @update:model-value="emit('close')">
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent>
      <el-form-item prop="identifier" label="用户名/邮箱">
        <el-input v-model="form.identifier" placeholder="用户名或邮箱" />
      </el-form-item>
      <el-form-item prop="role" label="角色">
        <el-select v-model="form.role">
          <el-option v-for="r in roles" :key="r" :label="r" :value="r" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" @click="onSubmit">添加</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from "vue"
import { type FormInstance, type FormRules } from "element-plus"
import type { Role } from "@/types/graph"

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: []; submit: [{ username?: string; email?: string; role: Role }] }>()

const roles: Role[] = ["admin", "editor", "viewer"]
const formRef = ref<FormInstance>()
const form = reactive({ identifier: "", role: "viewer" as Role })
const rules: FormRules = {
  identifier: [{ required: true, message: "请输入用户名或邮箱", trigger: "blur" }],
}

watch(() => props.visible, (v) => { if (v) { form.identifier = ""; form.role = "viewer" } })

async function onSubmit() {
  if (!(await formRef.value?.validate().catch(() => false))) return
  const id = form.identifier.trim()
  const body = id.includes("@") ? { email: id, role: form.role } : { username: id, role: form.role }
  emit("submit", body)
}
</script>
```

- [ ] **Step 3: 创建 `frontend/src/views/MembersView.vue`**

```vue
<template>
  <div>
    <div class="bar">
      <h3>成员</h3>
      <el-button v-if="proj.can('admin')" type="primary" @click="dialogVisible = true">添加成员</el-button>
    </div>
    <el-table :data="members" v-loading="loading">
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="display_name" label="显示名" />
      <el-table-column label="角色" width="160">
        <template #default="{ row }">
          <el-select
            v-if="proj.can('admin') && row.role !== 'owner'"
            :model-value="row.role" @change="(r) => onChangeRole(row, r)"
          >
            <el-option v-for="r in roles" :key="r" :label="r" :value="r" />
          </el-select>
          <span v-else>{{ row.role }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
            v-if="proj.can('admin') && row.role !== 'owner'"
            link type="danger" @click="onRemove(row)"
          >移除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <MemberFormDialog :visible="dialogVisible" @close="dialogVisible = false" @submit="onAdd" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { membersApi } from "@/api/members"
import { useProjectStore } from "@/stores/project"
import type { Member, Role } from "@/types/graph"
import MemberFormDialog from "@/components/MemberFormDialog.vue"

const route = useRoute()
const proj = useProjectStore()
const pid = computed(() => Number(route.params.pid))
const members = ref<Member[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const roles: Role[] = ["admin", "editor", "viewer"]

async function reload() {
  loading.value = true
  try {
    members.value = await membersApi.list(pid.value)
  } finally {
    loading.value = false
  }
}
onMounted(reload)

async function onAdd(body: { username?: string; email?: string; role: Role }) {
  await membersApi.add(pid.value, body)
  dialogVisible.value = false
  ElMessage.success("已添加")
  await reload()
}
async function onChangeRole(row: Member, role: Role) {
  await membersApi.changeRole(pid.value, row.user_id, role)
  ElMessage.success("角色已更新")
  await reload()
}
async function onRemove(row: Member) {
  await ElMessageBox.confirm(`移除成员「${row.username}」？`, "确认", { type: "warning" })
  await membersApi.remove(pid.value, row.user_id)
  ElMessage.success("已移除")
  await reload()
}
</script>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; }
</style>
```

- [ ] **Step 4: 改 `frontend/src/router/index.ts` — 把 /projects/:pid 接进 ProjectLayout 子路由**

把 Task 2 加的 `{ path: "/projects", ... }` 之后追加：
```ts
  {
    path: "/projects/:pid",
    component: () => import("@/views/ProjectLayout.vue"),
    children: [
      { path: "", redirect: (to) => `/projects/${to.params.pid}/members` },
      { path: "members", name: "members", component: () => import("@/views/MembersView.vue") },
      { path: "schemas", name: "schemas", component: () => import("@/views/SchemasView.vue") },
    ],
  },
```
> 注：`SchemasView.vue` 在 Task 4 创建。若本任务先跑 build 会因缺该文件失败——故本任务**不跑 build**，只跑 test；build 在 Task 4 末尾整体绿。或本任务临时占位：先不加 `schemas` 子路由，Task 4 再加。**采用后者**：本任务 children 只放 `""` 重定向 + `members`，Task 4 加 `schemas`。

修正：本任务 children 为：
```ts
    children: [
      { path: "", redirect: (to) => `/projects/${to.params.pid}/members` },
      { path: "members", name: "members", component: () => import("@/views/MembersView.vue") },
    ],
```

- [ ] **Step 5: 写测试 `frontend/tests/ProjectLayout.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"

const load = vi.fn()
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
```

- [ ] **Step 6: 写测试 `frontend/tests/MembersView.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"

const api = { list: vi.fn(), add: vi.fn(), changeRole: vi.fn(), remove: vi.fn() }
vi.mock("@/api/members", () => ({ membersApi: api }))
vi.mock("vue-router", () => ({ useRoute: () => ({ params: { pid: "1" } }) }))
let canResult = true
vi.mock("@/stores/project", () => ({ useProjectStore: () => ({ can: () => canResult }) }))
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { success: vi.fn() }, ElMessageBox: { confirm: vi.fn().mockResolvedValue(true) } }
})

import MembersView from "@/views/MembersView.vue"

const MEMBERS = [
  { user_id: 1, username: "owner", display_name: null, role: "owner" },
  { user_id: 2, username: "bob", display_name: null, role: "viewer" },
]

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  canResult = true
  api.list.mockResolvedValue(MEMBERS)
})

async function mountView() {
  const w = mount(MembersView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

it("渲染成员列表", async () => {
  const w = await mountView()
  expect(w.text()).toContain("owner")
  expect(w.text()).toContain("bob")
})

it("admin 可见添加成员按钮", async () => {
  canResult = true
  const w = await mountView()
  expect(w.findAll("button").some((b) => b.text() === "添加成员")).toBe(true)
})

it("非 admin 不显示添加成员按钮", async () => {
  canResult = false
  const w = await mountView()
  expect(w.findAll("button").some((b) => b.text() === "添加成员")).toBe(false)
})

it("移除非 owner 成员调 remove", async () => {
  api.remove.mockResolvedValue(undefined)
  const w = await mountView()
  await w.findAll("button").find((b) => b.text() === "移除")!.trigger("click")
  await flushPromises()
  expect(api.remove).toHaveBeenCalledWith(1, 2)
})
```

- [ ] **Step 7: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -8`
Expected: 全绿（27 + 本任务 5 = 32）。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/views/ProjectLayout.vue frontend/src/views/MembersView.vue frontend/src/components/MemberFormDialog.vue frontend/src/router/index.ts frontend/tests/ProjectLayout.spec.ts frontend/tests/MembersView.spec.ts
git commit -m "feat(frontend): F2 ProjectLayout 壳与成员管理（RBAC 显隐）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 4: SchemaForm + Schema 管理 + 构建

**Files:**
- Create: `frontend/src/components/SchemaForm.vue`, `frontend/src/views/SchemasView.vue`
- Modify: `frontend/src/router/index.ts`
- Test: `frontend/tests/SchemaForm.spec.ts`, `frontend/tests/SchemasView.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/components/SchemaForm.vue`**

```vue
<template>
  <el-dialog :model-value="visible" :title="isEdit ? '编辑 Schema' : '新建 Schema'" width="720" @update:model-value="emit('close')">
    <el-form @submit.prevent>
      <el-form-item label="type_key">
        <el-input v-model="typeKey" :disabled="isEdit" placeholder="如 data_task" />
      </el-form-item>
      <el-form-item label="显示名">
        <el-input v-model="displayName" placeholder="如 数据任务" />
      </el-form-item>
    </el-form>

    <el-divider>字段</el-divider>
    <div v-for="(f, i) in fields" :key="i" class="field-row">
      <el-input v-model="f.name" placeholder="name" style="width: 120px" />
      <el-input v-model="f.label" placeholder="label" style="width: 120px" />
      <el-select v-model="f.type" style="width: 110px">
        <el-option v-for="t in fieldTypes" :key="t" :label="t" :value="t" />
      </el-select>
      <el-switch v-model="f.required" active-text="必填" />
      <el-input v-if="f.type === 'enum'" v-model="f.optionsText" placeholder="选项,逗号分隔" style="width: 180px" />
      <el-button link type="danger" @click="removeField(i)">删除</el-button>
    </div>
    <el-button @click="addField">添加字段</el-button>

    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" @click="onSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from "vue"
import { ElMessage } from "element-plus"
import type { FieldType, NodeTypeSchema, SchemaField } from "@/types/graph"

interface FieldRow { name: string; label: string; type: FieldType; required: boolean; optionsText: string }

const props = defineProps<{ visible: boolean; isEdit: boolean; schema?: NodeTypeSchema | null }>()
const emit = defineEmits<{ close: []; submit: [{ type_key: string; display_name: string; fields: SchemaField[] }] }>()

const fieldTypes: FieldType[] = ["string", "number", "url", "enum", "bool"]
const typeKey = ref("")
const displayName = ref("")
const fields = reactive<FieldRow[]>([])

watch(() => props.visible, (v) => {
  if (!v) return
  typeKey.value = props.schema?.type_key ?? ""
  displayName.value = props.schema?.display_name ?? ""
  fields.splice(0, fields.length,
    ...(props.schema?.fields ?? []).map((f) => ({
      name: f.name, label: f.label, type: f.type, required: f.required,
      optionsText: (f.options ?? []).join(","),
    })),
  )
})

function addField() {
  fields.push({ name: "", label: "", type: "string", required: false, optionsText: "" })
}
function removeField(i: number) {
  fields.splice(i, 1)
}

function onSubmit() {
  if (!props.isEdit && !typeKey.value.trim()) return ElMessage.warning("请输入 type_key")
  if (!displayName.value.trim()) return ElMessage.warning("请输入显示名")
  const names = new Set<string>()
  const out: SchemaField[] = []
  for (const f of fields) {
    if (!f.name.trim()) return ElMessage.warning("字段 name 不能为空")
    if (names.has(f.name)) return ElMessage.warning(`字段 name 重复: ${f.name}`)
    names.add(f.name)
    let options: string[] | null = null
    if (f.type === "enum") {
      options = f.optionsText.split(",").map((s) => s.trim()).filter(Boolean)
      if (options.length === 0) return ElMessage.warning(`enum 字段 ${f.name} 需至少一个选项`)
    }
    out.push({ name: f.name.trim(), label: f.label.trim() || f.name.trim(), type: f.type, required: f.required, options })
  }
  emit("submit", { type_key: typeKey.value.trim(), display_name: displayName.value.trim(), fields: out })
}
</script>

<style scoped>
.field-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
</style>
```

- [ ] **Step 2: 创建 `frontend/src/views/SchemasView.vue`**

```vue
<template>
  <div>
    <div class="bar">
      <h3>类型 Schema</h3>
      <el-button v-if="proj.can('editor')" type="primary" @click="openCreate">新建 Schema</el-button>
    </div>
    <el-table :data="schemas" v-loading="loading">
      <el-table-column prop="type_key" label="type_key" />
      <el-table-column prop="display_name" label="显示名" />
      <el-table-column label="字段数" width="100">
        <template #default="{ row }">{{ row.fields.length }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button v-if="proj.can('editor')" link @click="openEdit(row)">编辑</el-button>
          <el-button v-if="proj.can('admin')" link type="danger" @click="onRemove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <SchemaForm
      :visible="dialogVisible" :is-edit="editing !== null" :schema="editing"
      @close="dialogVisible = false" @submit="onSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { schemasApi } from "@/api/schemas"
import { useProjectStore } from "@/stores/project"
import type { NodeTypeSchema, SchemaField } from "@/types/graph"
import SchemaForm from "@/components/SchemaForm.vue"

const route = useRoute()
const proj = useProjectStore()
const pid = computed(() => Number(route.params.pid))
const schemas = ref<NodeTypeSchema[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref<NodeTypeSchema | null>(null)

async function reload() {
  loading.value = true
  try {
    schemas.value = await schemasApi.list(pid.value)
  } finally {
    loading.value = false
  }
}
onMounted(reload)

function openCreate() {
  editing.value = null
  dialogVisible.value = true
}
function openEdit(row: NodeTypeSchema) {
  editing.value = row
  dialogVisible.value = true
}
async function onSubmit(body: { type_key: string; display_name: string; fields: SchemaField[] }) {
  if (editing.value) {
    await schemasApi.update(pid.value, editing.value.type_key, { display_name: body.display_name, fields: body.fields })
  } else {
    await schemasApi.create(pid.value, body)
  }
  dialogVisible.value = false
  ElMessage.success("已保存")
  await reload()
}
async function onRemove(row: NodeTypeSchema) {
  await ElMessageBox.confirm(`删除 schema「${row.type_key}」？`, "确认", { type: "warning" })
  await schemasApi.remove(pid.value, row.type_key)
  ElMessage.success("已删除")
  await reload()
}
</script>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; }
</style>
```

- [ ] **Step 3: 改 `frontend/src/router/index.ts` — 给 /projects/:pid 的 children 加 schemas 子路由**

在 children 数组的 `members` 之后追加：
```ts
      { path: "schemas", name: "schemas", component: () => import("@/views/SchemasView.vue") },
```

- [ ] **Step 4: 写测试 `frontend/tests/SchemaForm.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { mount } from "@vue/test-utils"
import ElementPlus from "element-plus"

const warn = vi.fn()
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { warning: warn } }
})

import SchemaForm from "@/components/SchemaForm.vue"

beforeEach(() => warn.mockReset())

function mountForm(props = {}) {
  return mount(SchemaForm, {
    props: { visible: true, isEdit: false, schema: null, ...props },
    global: { plugins: [ElementPlus] },
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
  // 初始渲染既有 schema：一个 enum 字段 + 一个 string 字段
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
  // enum 行含 options 占位输入，string 行不含
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
  await inputs[0].setValue("engine") // name
  await inputs[1].setValue("引擎")   // label
  await w.findAll("button").find((b) => b.text() === "保存")!.trigger("click")
  const emitted = w.emitted("submit")
  expect(emitted).toBeTruthy()
  const payload = emitted![0][0] as { fields: { name: string; options: unknown }[] }
  expect(payload.fields[0].name).toBe("engine")
  expect(payload.fields[0].options).toBeNull()
})
```

- [ ] **Step 5: 写测试 `frontend/tests/SchemasView.spec.ts`**

```ts
import { it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import ElementPlus from "element-plus"

const api = { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() }
vi.mock("@/api/schemas", () => ({ schemasApi: api }))
vi.mock("vue-router", () => ({ useRoute: () => ({ params: { pid: "1" } }) }))
let canResult = true
vi.mock("@/stores/project", () => ({ useProjectStore: () => ({ can: () => canResult }) }))
vi.mock("element-plus", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, ElMessage: { success: vi.fn() }, ElMessageBox: { confirm: vi.fn().mockResolvedValue(true) } }
})

import SchemasView from "@/views/SchemasView.vue"

const SCHEMAS = [{ id: "s1", type_key: "data_task", display_name: "数据任务", fields: [], created_at: "", updated_at: "" }]

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  canResult = true
  api.list.mockResolvedValue(SCHEMAS)
})

async function mountView() {
  const w = mount(SchemasView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

it("渲染 schema 列表", async () => {
  const w = await mountView()
  expect(w.text()).toContain("data_task")
})

it("editor 可见新建按钮", async () => {
  canResult = true
  const w = await mountView()
  expect(w.findAll("button").some((b) => b.text() === "新建 Schema")).toBe(true)
})

it("viewer 不显示新建按钮", async () => {
  canResult = false
  const w = await mountView()
  expect(w.findAll("button").some((b) => b.text() === "新建 Schema")).toBe(false)
})
```

- [ ] **Step 6: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -10`
Expected: 全绿（32 + 本任务 7 = 39）。

- [ ] **Step 7: 类型检查 + 构建（F2 DoD 闸门）**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run build 2>&1 | tail -10`
Expected: vue-tsc 无类型错误，vite build 产出 dist/。常见需修：未用 import、`defineProps`/`defineEmits` 泛型、Element Plus 组件类型。按报错精确修，不放宽 strict。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/components/SchemaForm.vue frontend/src/views/SchemasView.vue frontend/src/router/index.ts frontend/tests/SchemaForm.spec.ts frontend/tests/SchemasView.spec.ts
git commit -m "feat(frontend): F2 Schema 管理与 SchemaForm 动态字段编辑器

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Phase F2 完成标准（Definition of Done）

- [ ] `npm run build`（vue-tsc）通过、无 TS 错误。
- [ ] `npm run test` 全绿（F1 既有 19 + F2 新增 20 = 39）。
- [ ] 手动：登录 → 项目列表建项目 → 进入项目 → 加成员/改角色/移除 → 建/改/删 schema（含 enum 字段）→ 归档/恢复/purge（输名确认）全流程走通。
- [ ] RBAC：viewer 看不到写按钮；越权时后端 403/409 被拦截器提示。
- [ ] `/` 重定向 `/projects`；未登录被守卫挡到 /login。

## 下一子项目预告（不在本计划内）

- F3：画布核心（X6）——ProjectLayout 加 `/projects/:pid` 画布主视图 + GraphCanvas + 节点/边交互 + 侧栏过滤。




