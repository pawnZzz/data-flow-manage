# 前端 F1：脚手架 + 认证 + API 基座 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `frontend/` Vite+Vue3+TS 工程基座 + 完整认证流（API 客户端含 JWT/统一错误、auth store、登录/注册/个人设置、路由守卫）。

**Architecture:** 分层 api(axios 客户端+端点封装) → stores(Pinia) → views/router。token 存 localStorage；dev 用 Vite proxy 转后端避开 CORS。单元+组件测试用 Vitest + @vue/test-utils，mock api 层。

**Tech Stack:** Vue 3 (`<script setup>` + TS)、Vite、Pinia、Vue Router、Element Plus、axios、Vitest、@vue/test-utils、jsdom、vue-tsc。

参考 spec：`docs/superpowers/specs/2026-06-09-frontend-f1-scaffold-auth-design.md`。

---

## File Structure

- `frontend/package.json`、`vite.config.ts`、`vitest.config.ts`、`tsconfig.json`、`tsconfig.node.json`、`index.html` — 工程配置。
- `frontend/src/main.ts` — 挂载 App + Pinia + router + Element Plus。
- `frontend/src/App.vue` — `<router-view/>` 壳。
- `frontend/src/types/auth.ts` — User/TokenResponse/RegisterPayload/ApiError 类型。
- `frontend/src/api/client.ts` — axios 实例 + JWT 请求拦截 + 错误响应归一化拦截。
- `frontend/src/api/auth.ts` — 认证端点封装。
- `frontend/src/stores/auth.ts` — Pinia 认证 store。
- `frontend/src/views/LoginView.vue` / `ProfileView.vue` — 视图。
- `frontend/src/router/index.ts` — 路由表 + 守卫。
- `frontend/tests/*.spec.ts` — Vitest 测试。

约定：命令在 `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend` 下跑；commit 在仓库根 `/Users/zyc/Data/App/obsidian/pawnZzz/tmp8`，message 末尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。Node ≥18。

## Task 1: 工程脚手架

**Files:**
- Create: `frontend/package.json`, `vite.config.ts`, `vitest.config.ts`, `tsconfig.json`, `tsconfig.node.json`, `index.html`, `src/main.ts`, `src/App.vue`, `src/types/auth.ts`
- Test: `frontend/tests/smoke.spec.ts`

- [ ] **Step 1: 创建 `frontend/package.json`**

```json
{
  "name": "lineage-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "axios": "^1.7.0",
    "element-plus": "^2.7.0",
    "pinia": "^2.1.0",
    "vue": "^3.4.0",
    "vue-router": "^4.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "@vue/test-utils": "^2.4.0",
    "jsdom": "^24.0.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vitest": "^1.6.0",
    "vue-tsc": "^2.0.0"
  }
}
```

- [ ] **Step 2: 创建 `frontend/tsconfig.json` 与 `frontend/tsconfig.node.json`**

`tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "types": ["vitest/globals"],
    "paths": { "@/*": ["./src/*"] },
    "baseUrl": "."
  },
  "include": ["src/**/*.ts", "src/**/*.vue", "tests/**/*.ts"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```
`tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "noEmit": true
  },
  "include": ["vite.config.ts", "vitest.config.ts"]
}
```

- [ ] **Step 3: 创建 `frontend/vite.config.ts`**

```ts
import { fileURLToPath, URL } from "node:url"
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
})
```

- [ ] **Step 4: 创建 `frontend/vitest.config.ts`**

```ts
import { fileURLToPath, URL } from "node:url"
import { defineConfig } from "vitest/config"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: { environment: "jsdom", globals: true },
})
```

- [ ] **Step 5: 创建 `frontend/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>任务血缘管理工具</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 6: 创建 `frontend/src/types/auth.ts`**

```ts
export interface User {
  id: number
  username: string
  email: string
  display_name: string | null
  status: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
  display_name?: string | null
}

export interface ApiError {
  status: number
  code: string
  message: string
  details: Record<string, unknown>
}
```

- [ ] **Step 7: 创建 `frontend/src/App.vue`**

```vue
<template>
  <router-view />
</template>

<script setup lang="ts"></script>
```

- [ ] **Step 8: 创建 `frontend/src/main.ts`**

```ts
import { createApp } from "vue"
import { createPinia } from "pinia"
import ElementPlus from "element-plus"
import "element-plus/dist/index.css"
import App from "./App.vue"
import router from "./router"

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount("#app")
```

> 注：`./router` 在 Task 3 创建。本任务的 smoke 测试不导入 main.ts，故不受影响；`npm run build` 在 Task 3 完成后才整体绿。本任务先验证 Vitest 跑通。

- [ ] **Step 9: 写 smoke 测试 `frontend/tests/smoke.spec.ts`**

```ts
import { describe, it, expect } from "vitest"
import { mount } from "@vue/test-utils"
import { defineComponent } from "vue"

describe("vitest + vue-test-utils 环境", () => {
  it("能挂载并渲染组件", () => {
    const C = defineComponent({ template: "<div class='x'>hi</div>" })
    const w = mount(C)
    expect(w.find(".x").text()).toBe("hi")
  })
})
```

- [ ] **Step 10: 安装依赖并跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm install 2>&1 | tail -3 && npm run test 2>&1 | tail -6`
Expected: `npm install` 成功；Vitest 1 passed。

- [ ] **Step 11: 创建 `frontend/.gitignore`**

```
node_modules/
dist/
*.local
```

- [ ] **Step 12: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/package.json frontend/package-lock.json frontend/*.ts frontend/*.json frontend/index.html frontend/.gitignore frontend/src/main.ts frontend/src/App.vue frontend/src/types frontend/tests/smoke.spec.ts
git commit -m "feat(frontend): F1 工程脚手架（Vite+Vue3+TS+Pinia+Element Plus+Vitest）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 2: API 客户端 + auth 端点 + Pinia store

**Files:**
- Create: `frontend/src/api/client.ts`, `frontend/src/api/auth.ts`, `frontend/src/stores/auth.ts`
- Test: `frontend/tests/client.spec.ts`, `frontend/tests/auth.store.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/api/client.ts`**

```ts
import axios, { AxiosError } from "axios"
import { ElMessage } from "element-plus"
import type { ApiError } from "@/types/auth"

const SILENT_PATHS = ["/auth/login", "/auth/register", "/auth/password"]

function isSilent(url: string | undefined): boolean {
  return !!url && SILENT_PATHS.some((p) => url.includes(p))
}

export const http = axios.create({ baseURL: "/api/v1" })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("token")
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<{ error?: { code: string; message: string; details: Record<string, unknown> } }>) => {
    const status = error.response?.status ?? 0
    const env = error.response?.data?.error
    const apiError: ApiError = {
      status,
      code: env?.code ?? "NETWORK_ERROR",
      message: env?.message ?? "服务暂不可用",
      details: env?.details ?? {},
    }
    const url = error.config?.url

    if (status === 401 && url?.includes("/auth/login")) {
      // 凭证错误：交给登录表单，不跳转不弹全局
      return Promise.reject(apiError)
    }
    if (status === 401) {
      localStorage.removeItem("token")
      window.location.assign("/login")
      return Promise.reject(apiError)
    }
    if (status === 403) {
      ElMessage.error(apiError.message || "无权限")
      return Promise.reject(apiError)
    }
    if (status === 0) {
      ElMessage.error("服务暂不可用")
      return Promise.reject(apiError)
    }
    if (!isSilent(url)) {
      ElMessage.error(apiError.message)
    }
    return Promise.reject(apiError)
  },
)
```

- [ ] **Step 2: 创建 `frontend/src/api/auth.ts`**

```ts
import { http } from "./client"
import type { RegisterPayload, TokenResponse, User } from "@/types/auth"

export const authApi = {
  login: (username: string, password: string) =>
    http.post("/auth/login", { username, password }) as unknown as Promise<TokenResponse>,
  register: (payload: RegisterPayload) =>
    http.post("/auth/register", payload) as unknown as Promise<User>,
  logout: () => http.post("/auth/logout") as unknown as Promise<void>,
  getMe: () => http.get("/auth/me") as unknown as Promise<User>,
  updateMe: (body: { display_name: string | null }) =>
    http.patch("/auth/me", body) as unknown as Promise<User>,
  changePassword: (body: { old_password: string; new_password: string }) =>
    http.post("/auth/password", body) as unknown as Promise<void>,
}
```

> 拦截器把成功响应解包为 `response.data`，故各方法返回的是数据本体；`as unknown as Promise<T>` 修正 axios 的静态返回类型。

- [ ] **Step 3: 创建 `frontend/src/stores/auth.ts`**

```ts
import { computed, ref } from "vue"
import { defineStore } from "pinia"
import { authApi } from "@/api/auth"
import type { RegisterPayload, User } from "@/types/auth"

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(localStorage.getItem("token"))
  const user = ref<User | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  function setToken(t: string | null) {
    token.value = t
    if (t) localStorage.setItem("token", t)
    else localStorage.removeItem("token")
  }

  async function fetchMe() {
    user.value = await authApi.getMe()
  }

  async function login(username: string, password: string) {
    const res = await authApi.login(username, password)
    setToken(res.access_token)
    await fetchMe()
  }

  async function register(payload: RegisterPayload) {
    await authApi.register(payload) // 不自动登录
  }

  async function updateProfile(display_name: string | null) {
    user.value = await authApi.updateMe({ display_name })
  }

  async function changePassword(old_password: string, new_password: string) {
    await authApi.changePassword({ old_password, new_password })
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      // 忽略登出接口失败，本地照常清理
    }
    setToken(null)
    user.value = null
  }

  return {
    token, user, isAuthenticated,
    setToken, fetchMe, login, register, updateProfile, changePassword, logout,
  }
})
```

- [ ] **Step 4: 写测试 `frontend/tests/client.spec.ts`**

```ts
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest"

const messages: string[] = []
vi.mock("element-plus", () => ({
  ElMessage: { error: (m: string) => messages.push(m) },
}))

beforeEach(() => {
  localStorage.clear()
  messages.length = 0
  vi.resetModules()
})

afterEach(() => {
  vi.restoreAllMocks()
})

async function loadClient() {
  const mod = await import("@/api/client")
  return mod.http
}

it("请求拦截器在有 token 时加 Bearer 头", async () => {
  localStorage.setItem("token", "abc")
  const http = await loadClient()
  const handler = (http.interceptors.request as any).handlers[0].fulfilled
  const cfg = handler({ headers: {} })
  expect(cfg.headers.Authorization).toBe("Bearer abc")
})

it("无 token 时不加 Authorization 头", async () => {
  const http = await loadClient()
  const handler = (http.interceptors.request as any).handlers[0].fulfilled
  const cfg = handler({ headers: {} })
  expect(cfg.headers.Authorization).toBeUndefined()
})

it("非登录路径 401 清 token 并跳转 /login", async () => {
  localStorage.setItem("token", "abc")
  const assign = vi.fn()
  vi.stubGlobal("location", { assign } as any)
  const http = await loadClient()
  const onRejected = (http.interceptors.response as any).handlers[0].rejected
  const err = {
    config: { url: "/auth/me" },
    response: { status: 401, data: { error: { code: "AUTH_ERROR", message: "过期", details: {} } } },
  }
  await expect(onRejected(err)).rejects.toMatchObject({ status: 401, code: "AUTH_ERROR" })
  expect(localStorage.getItem("token")).toBeNull()
  expect(assign).toHaveBeenCalledWith("/login")
})

it("登录路径 401 不跳转不弹全局，仅归一化抛出", async () => {
  const assign = vi.fn()
  vi.stubGlobal("location", { assign } as any)
  const http = await loadClient()
  const onRejected = (http.interceptors.response as any).handlers[0].rejected
  const err = {
    config: { url: "/auth/login" },
    response: { status: 401, data: { error: { code: "AUTH_ERROR", message: "凭证错误", details: {} } } },
  }
  await expect(onRejected(err)).rejects.toMatchObject({ code: "AUTH_ERROR" })
  expect(assign).not.toHaveBeenCalled()
  expect(messages).toEqual([])
})

it("非静默路径其他错误弹全局消息", async () => {
  const http = await loadClient()
  const onRejected = (http.interceptors.response as any).handlers[0].rejected
  const err = {
    config: { url: "/nodes" },
    response: { status: 409, data: { error: { code: "CONFLICT", message: "冲突", details: {} } } },
  }
  await expect(onRejected(err)).rejects.toMatchObject({ status: 409 })
  expect(messages).toContain("冲突")
})
```

- [ ] **Step 5: 写测试 `frontend/tests/auth.store.spec.ts`**

```ts
import { describe, it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"

const api = {
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  getMe: vi.fn(),
  updateMe: vi.fn(),
  changePassword: vi.fn(),
}
vi.mock("@/api/auth", () => ({ authApi: api }))

import { useAuthStore } from "@/stores/auth"

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  Object.values(api).forEach((f) => f.mockReset())
})

it("login 存 token 到 state+localStorage 并拉取 user", async () => {
  api.login.mockResolvedValue({ access_token: "tk", token_type: "bearer" })
  api.getMe.mockResolvedValue({ id: 1, username: "u", email: "u@x.com", display_name: null, status: "active" })
  const store = useAuthStore()
  await store.login("u", "p")
  expect(store.token).toBe("tk")
  expect(localStorage.getItem("token")).toBe("tk")
  expect(store.user?.username).toBe("u")
  expect(store.isAuthenticated).toBe(true)
})

it("register 不自动登录", async () => {
  api.register.mockResolvedValue({ id: 1, username: "u", email: "u@x.com", display_name: null, status: "active" })
  const store = useAuthStore()
  await store.register({ username: "u", email: "u@x.com", password: "secret" })
  expect(store.isAuthenticated).toBe(false)
  expect(api.login).not.toHaveBeenCalled()
})

it("logout 清空 token+user", async () => {
  api.logout.mockResolvedValue(undefined)
  const store = useAuthStore()
  store.setToken("tk")
  store.user = { id: 1, username: "u", email: "u@x.com", display_name: null, status: "active" }
  await store.logout()
  expect(store.token).toBeNull()
  expect(localStorage.getItem("token")).toBeNull()
  expect(store.user).toBeNull()
})

it("logout 即便接口失败也清本地", async () => {
  api.logout.mockRejectedValue(new Error("boom"))
  const store = useAuthStore()
  store.setToken("tk")
  await store.logout()
  expect(store.token).toBeNull()
})
```

- [ ] **Step 6: 跑测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -8`
Expected: 全绿（smoke 1 + client 5 + store 4 = 10）。

- [ ] **Step 7: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/api frontend/src/stores frontend/tests/client.spec.ts frontend/tests/auth.store.spec.ts
git commit -m "feat(frontend): F1 API 客户端（JWT+错误归一化）与 auth store

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 3: 视图 + 路由守卫 + 组件测试

**Files:**
- Create: `frontend/src/views/LoginView.vue`, `frontend/src/views/ProfileView.vue`, `frontend/src/router/index.ts`
- Test: `frontend/tests/LoginView.spec.ts`, `frontend/tests/ProfileView.spec.ts`, `frontend/tests/router.guard.spec.ts`

- [ ] **Step 1: 创建 `frontend/src/router/index.ts`**

```ts
import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "login", component: () => import("@/views/LoginView.vue"), meta: { public: true } },
  { path: "/profile", name: "profile", component: () => import("@/views/ProfileView.vue") },
  { path: "/", redirect: "/profile" },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthenticated) return { name: "login" }
  if (to.name === "login" && auth.isAuthenticated) return { path: "/" }
  return true
})

export default router
```

- [ ] **Step 2: 创建 `frontend/src/views/LoginView.vue`**

```vue
<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login">
          <el-form ref="loginForm" :model="loginData" :rules="loginRules" @submit.prevent>
            <el-form-item prop="username">
              <el-input v-model="loginData.username" placeholder="用户名" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginData.password" type="password" placeholder="密码" show-password />
            </el-form-item>
            <el-alert v-if="loginError" :title="loginError" type="error" :closable="false" />
            <el-button type="primary" :loading="busy" @click="onLogin">登录</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form ref="regForm" :model="regData" :rules="regRules" @submit.prevent>
            <el-form-item prop="username">
              <el-input v-model="regData.username" placeholder="用户名（≥3）" />
            </el-form-item>
            <el-form-item prop="email">
              <el-input v-model="regData.email" placeholder="邮箱" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="regData.password" type="password" placeholder="密码（≥6）" show-password />
            </el-form-item>
            <el-form-item prop="display_name">
              <el-input v-model="regData.display_name" placeholder="显示名（可选）" />
            </el-form-item>
            <el-alert v-if="regError" :title="regError" type="error" :closable="false" />
            <el-button type="primary" :loading="busy" @click="onRegister">注册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { ElMessage, type FormInstance } from "element-plus"
import { useAuthStore } from "@/stores/auth"
import type { ApiError } from "@/types/auth"

const router = useRouter()
const auth = useAuthStore()
const tab = ref("login")
const busy = ref(false)

const loginForm = ref<FormInstance>()
const regForm = ref<FormInstance>()
const loginData = reactive({ username: "", password: "" })
const regData = reactive({ username: "", email: "", password: "", display_name: "" })
const loginError = ref("")
const regError = ref("")

const loginRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
}
const regRules = {
  username: [{ required: true, min: 3, message: "用户名至少 3 位", trigger: "blur" }],
  email: [{ required: true, type: "email", message: "邮箱格式不正确", trigger: "blur" }],
  password: [{ required: true, min: 6, message: "密码至少 6 位", trigger: "blur" }],
}

async function onLogin() {
  if (!(await loginForm.value?.validate().catch(() => false))) return
  loginError.value = ""
  busy.value = true
  try {
    await auth.login(loginData.username, loginData.password)
    router.push("/")
  } catch (e) {
    loginError.value = (e as ApiError).status === 401 ? "用户名或密码错误" : (e as ApiError).message
  } finally {
    busy.value = false
  }
}

async function onRegister() {
  if (!(await regForm.value?.validate().catch(() => false))) return
  regError.value = ""
  busy.value = true
  try {
    await auth.register({
      username: regData.username, email: regData.email,
      password: regData.password, display_name: regData.display_name || null,
    })
    ElMessage.success("注册成功，请登录")
    tab.value = "login"
  } catch (e) {
    const err = e as ApiError
    regError.value = err.status === 403 ? "注册已关闭"
      : err.status === 409 ? "用户名或邮箱已被占用" : err.message
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.login-wrap { display: flex; justify-content: center; padding-top: 80px; }
.login-card { width: 380px; }
</style>
```

- [ ] **Step 3: 创建 `frontend/src/views/ProfileView.vue`**

```vue
<template>
  <div class="profile-wrap" v-if="auth.user">
    <el-card>
      <template #header>
        <span>个人设置</span>
        <el-button class="logout-btn" link type="danger" @click="onLogout">登出</el-button>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户名">{{ auth.user.username }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ auth.user.email }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ auth.user.status }}</el-descriptions-item>
      </el-descriptions>

      <el-divider>修改显示名</el-divider>
      <el-input v-model="displayName" placeholder="显示名" />
      <el-button type="primary" :loading="busy" @click="onSaveName">保存</el-button>

      <el-divider>修改密码</el-divider>
      <el-form ref="pwForm" :model="pw" :rules="pwRules" @submit.prevent>
        <el-form-item prop="old_password">
          <el-input v-model="pw.old_password" type="password" placeholder="原密码" show-password />
        </el-form-item>
        <el-form-item prop="new_password">
          <el-input v-model="pw.new_password" type="password" placeholder="新密码（≥6）" show-password />
        </el-form-item>
        <el-button type="primary" :loading="busy" @click="onChangePw">修改密码</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { ElMessage, type FormInstance } from "element-plus"
import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()
const router = useRouter()
const busy = ref(false)
const displayName = ref("")
const pwForm = ref<FormInstance>()
const pw = reactive({ old_password: "", new_password: "" })
const pwRules = {
  old_password: [{ required: true, message: "请输入原密码", trigger: "blur" }],
  new_password: [{ required: true, min: 6, message: "新密码至少 6 位", trigger: "blur" }],
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  displayName.value = auth.user?.display_name ?? ""
})

async function onSaveName() {
  busy.value = true
  try {
    await auth.updateProfile(displayName.value || null)
    ElMessage.success("已保存")
  } finally {
    busy.value = false
  }
}

async function onChangePw() {
  if (!(await pwForm.value?.validate().catch(() => false))) return
  busy.value = true
  try {
    await auth.changePassword(pw.old_password, pw.new_password)
    ElMessage.success("密码已修改")
    pw.old_password = ""
    pw.new_password = ""
  } finally {
    busy.value = false
  }
}

async function onLogout() {
  await auth.logout()
  router.push("/login")
}
</script>

<style scoped>
.profile-wrap { max-width: 560px; margin: 40px auto; }
.logout-btn { float: right; }
</style>
```

- [ ] **Step 4: 写测试 `frontend/tests/LoginView.spec.ts`**

```ts
import { describe, it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import { setActivePinia, createPinia } from "pinia"
import ElementPlus from "element-plus"

const login = vi.fn()
const register = vi.fn()
vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ login, register }),
}))
const push = vi.fn()
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }))

import LoginView from "@/views/LoginView.vue"

function mountView() {
  return mount(LoginView, { global: { plugins: [ElementPlus] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  login.mockReset(); register.mockReset(); push.mockReset()
})

it("渲染登录与注册 tab", () => {
  const w = mountView()
  expect(w.text()).toContain("登录")
  expect(w.text()).toContain("注册")
})

it("有效登录调 store.login 并跳转", async () => {
  login.mockResolvedValue(undefined)
  const w = mountView()
  await w.findAll("input")[0].setValue("alice")
  await w.findAll("input")[1].setValue("secret")
  await w.find("button").trigger("click")
  await flushPromises()
  expect(login).toHaveBeenCalledWith("alice", "secret")
  expect(push).toHaveBeenCalledWith("/")
})

it("登录失败(401)就地显示错误", async () => {
  login.mockRejectedValue({ status: 401, code: "AUTH_ERROR", message: "x", details: {} })
  const w = mountView()
  await w.findAll("input")[0].setValue("alice")
  await w.findAll("input")[1].setValue("bad")
  await w.find("button").trigger("click")
  await flushPromises()
  expect(w.text()).toContain("用户名或密码错误")
  expect(push).not.toHaveBeenCalled()
})
```

- [ ] **Step 5: 写测试 `frontend/tests/ProfileView.spec.ts`**

```ts
import { describe, it, expect, beforeEach, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import { setActivePinia, createPinia } from "pinia"
import ElementPlus from "element-plus"

const updateProfile = vi.fn()
const changePassword = vi.fn()
const logout = vi.fn()
const fetchMe = vi.fn()
const store = {
  user: { id: 1, username: "alice", email: "a@x.com", display_name: "A", status: "active" },
  updateProfile, changePassword, logout, fetchMe,
}
vi.mock("@/stores/auth", () => ({ useAuthStore: () => store }))
const push = vi.fn()
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }))

import ProfileView from "@/views/ProfileView.vue"

function mountView() {
  return mount(ProfileView, { global: { plugins: [ElementPlus] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  ;[updateProfile, changePassword, logout, fetchMe, push].forEach((f) => f.mockReset())
})

it("渲染用户信息", () => {
  const w = mountView()
  expect(w.text()).toContain("alice")
  expect(w.text()).toContain("a@x.com")
})

it("保存显示名调 updateProfile", async () => {
  updateProfile.mockResolvedValue(undefined)
  const w = mountView()
  await w.findAll("button").find((b) => b.text() === "保存")!.trigger("click")
  await flushPromises()
  expect(updateProfile).toHaveBeenCalledWith("A")
})

it("登出调 logout 并跳登录", async () => {
  logout.mockResolvedValue(undefined)
  const w = mountView()
  await w.findAll("button").find((b) => b.text() === "登出")!.trigger("click")
  await flushPromises()
  expect(logout).toHaveBeenCalled()
  expect(push).toHaveBeenCalledWith("/login")
})
```

- [ ] **Step 6: 写测试 `frontend/tests/router.guard.spec.ts`**

```ts
import { describe, it, expect, beforeEach, vi } from "vitest"
import { setActivePinia, createPinia } from "pinia"

let authed = false
vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ get isAuthenticated() { return authed } }),
}))

import router from "@/router"

beforeEach(() => {
  setActivePinia(createPinia())
  authed = false
})

it("未登录访问 /profile 重定向 /login", async () => {
  authed = false
  await router.push("/profile")
  await router.isReady()
  expect(router.currentRoute.value.name).toBe("login")
})

it("已登录访问 /login 重定向到 /", async () => {
  authed = true
  await router.push("/login")
  await router.isReady()
  expect(router.currentRoute.value.path).toBe("/profile")
})
```

- [ ] **Step 7: 跑全部测试**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run test 2>&1 | tail -10`
Expected: 全绿（smoke 1 + client 5 + store 4 + LoginView 3 + ProfileView 3 + guard 2 = 18）。

- [ ] **Step 8: 类型检查 + 构建**

Run: `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/frontend && npm run build 2>&1 | tail -8`
Expected: vue-tsc 无类型错误，vite build 成功产出 dist/。若个别 Element Plus 类型导入报错，按报错精确修（不放宽 strict）。

- [ ] **Step 9: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add frontend/src/views frontend/src/router frontend/tests/LoginView.spec.ts frontend/tests/ProfileView.spec.ts frontend/tests/router.guard.spec.ts
git commit -m "feat(frontend): F1 登录/注册/个人设置视图与路由守卫

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Phase F1 完成标准（Definition of Done）

- [ ] `npm install` 后 `npm run build`（含 vue-tsc 类型检查）通过、无 TS 错误。
- [ ] `npm run test`（Vitest）全绿（18 个）。
- [ ] 手动：起后端 + `npm run dev`，注册 → 登录 → /profile → 改 display_name → 改密码 → 登出，全流程经 dev proxy 走通。
- [ ] 刷新不掉登录（token 持久）；未登录访问 /profile 被守卫挡到 /login。
- [ ] 拦截器：登录 401 就地提示、其他 401 跳登录、静默路径不弹重复全局。

## 下一子项目预告（不在本计划内）

- F2：项目列表 + 成员管理 + Schema 管理，复用 F1 的 client/store/守卫。



