# 任务血缘工具 前端 F1：脚手架 + 认证 + API 基座 — 设计文档

**日期：** 2026-06-09
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§7 前端结构、§8 错误处理）
**前置：** 后端 Phase 1-3 全部完成（认证/RBAC/图/导入导出），API 在 `/api/v1`。

## 背景与拆分

前端（master §7）是大子系统，拆为 5 个有序子项目，各自 spec→plan→实现：
- **F1（本文档）**：脚手架 + 认证 + API 基座。
- F2：项目 + 成员 + Schema 管理。
- F3：画布核心（X6）。
- F4：属性面板 + 影响分析可视化。
- F5：SQL 导入 + 文件导入导出入口。

F1 是地基：工程脚手架、API 客户端（JWT + 统一错误）、认证 store、登录/注册/个人设置、路由守卫。

## 目标

建立可运行可测的前端工程基座 + 完整认证流，后续子项目在其上扩展。

## 范围

**做：**
- `frontend/` Vite + Vue3(`<script setup>`+TS) 工程；Pinia、Vue Router、Element Plus、Vitest + @vue/test-utils。
- `api/client.ts`：axios 实例 + JWT 请求拦截器 + 统一错误响应拦截器。
- `api/auth.ts`：register/login/logout/getMe/updateMe/changePassword。
- `stores/auth.ts`：token（localStorage 持久）+ 当前用户 + 认证 actions。
- `views/LoginView.vue`（登录+注册 tab）、`views/ProfileView.vue`（改资料+改密+登出）。
- `router/`：路由表 + 守卫（未登录跳 /login）。
- App 壳 + main.ts。

**不做（留 F2+）：**
- 项目/成员/schema/画布/导入导出 UI。
- 路由根 `/` 暂重定向到 `/profile`（F2 引入 /projects 后改）。
- 审计日志页（master §7.1 的 /audit，后端审计仅 logger，暂不做页面）。

## 决策（已与用户确认）

- **技术栈**：Vue3 + TypeScript + Pinia + Vue Router + Element Plus + Vite + Vitest + @vue/test-utils（对齐 master §7）。
- **Token 存储**：localStorage（后端无 refresh token、720min 过期；刷新/多标签保持登录；与 master §7.5 用 localStorage 一致；接受 SPA 常规 XSS 暴露）。
- **测试范围**：单元 + 组件（拦截器、store、LoginView/ProfileView 渲染与提交、路由守卫）。
- **dev 联调**：Vite proxy `/api` → `http://localhost:8000`，axios `baseURL=/api/v1`，避开 CORS。

## 后端认证契约（对齐）

| 端点 | 请求 | 响应 |
|------|------|------|
| `POST /api/v1/auth/register` | {username≥3, email, password≥6, display_name?} | 201 User |
| `POST /api/v1/auth/login` | {username, password} | {access_token, token_type} |
| `POST /api/v1/auth/logout` | — | 204 |
| `GET /api/v1/auth/me` | — | User |
| `PATCH /api/v1/auth/me` | {display_name?} | User |
| `POST /api/v1/auth/password` | {old_password, new_password≥6} | 204 |

`User = {id, username, email, display_name, status}`。错误信封 `{error:{code, message, details}}`。注册关闭时 register → 403。

## 1. 文件结构

```
frontend/
├── index.html
├── package.json          # vue, vue-router, pinia, element-plus, axios; dev: vite, vitest, @vue/test-utils, jsdom, typescript, vue-tsc
├── vite.config.ts        # @vitejs/plugin-vue + dev proxy /api → :8000
├── vitest.config.ts      # environment jsdom, globals
├── tsconfig.json
└── src/
    ├── main.ts           # createApp + Pinia + router + ElementPlus，挂载 #app
    ├── App.vue           # <router-view/>
    ├── api/
    │   ├── client.ts     # axios 实例 + JWT 请求拦截 + 错误响应拦截/归一化
    │   └── auth.ts        # 认证端点封装
    ├── stores/
    │   └── auth.ts        # Pinia：token + user + 认证 actions
    ├── views/
    │   ├── LoginView.vue
    │   └── ProfileView.vue
    ├── router/
    │   └── index.ts       # 路由表 + beforeEach 守卫
    └── types/
        └── auth.ts        # User / TokenResponse / 请求体类型
└── tests/
    ├── client.spec.ts  auth.store.spec.ts  LoginView.spec.ts
    ├── ProfileView.spec.ts  router.guard.spec.ts
```

## 2. API 客户端 `api/client.ts`

axios 实例 `baseURL: "/api/v1"`，两拦截器：
- **请求**：`localStorage.getItem("token")` 有则设 `Authorization: Bearer <token>`。
- **响应**：成功返回 `response.data`；失败归一化为 `ApiError{status, code, message, details}`（从 `error.response.data.error` 取；无信封用兜底文案）。处理规则（顺序）：
  1. **`401` 且请求路径 == `/auth/login`** → 凭证错误，**不跳转、不弹全局**，仅 reject（登录表单就地显示）。
  2. **其他 `401`**（会话过期）→ 清 token + `window.location.assign("/login")`。
  3. `403` → `ElMessage.error(message || "无权限")`。
  4. 网络错误/无信封 → `ElMessage.error("服务暂不可用")`。
  5. 其他状态码：若路径在**静默白名单** `[/auth/login, /auth/register, /auth/password]` → 不弹全局（表单就地处理）；否则 `ElMessage.error(message)`。
  - 始终 `reject(ApiError)`，调用方可 catch。

> 拦截器不 import router（避免循环依赖）：跳转用 `window.location.assign("/login")`，token 清理直接 `localStorage.removeItem`。静默白名单让登录/注册/改密的 4xx（401 凭证错、409 占用、400 旧密码错）由表单就地提示，不弹重复全局消息；非登录路径的 401（过期）仍统一跳登录。

## 3. `api/auth.ts`

```ts
login(username, password): Promise<TokenResponse>
register(payload: RegisterPayload): Promise<User>
logout(): Promise<void>
getMe(): Promise<User>
updateMe(body: {display_name: string|null}): Promise<User>
changePassword(body: {old_password, new_password}): Promise<void>
```
全部经 client，路径 `/auth/*`。

## 4. Pinia `stores/auth.ts`（setup store）

- state：`token = ref(localStorage.getItem("token"))`、`user = ref<User|null>(null)`。
- getter：`isAuthenticated = computed(() => !!token.value)`。
- actions：
  - `setToken(t)`：写 `token.value` + `localStorage`（null 则 removeItem）。
  - `login(u,p)`：`auth.login` → `setToken(access_token)` → `fetchMe()`。
  - `register(payload)`：`auth.register`（不自动登录，返回成功供视图切登录 tab）。
  - `fetchMe()`：`auth.getMe` → `user.value`。
  - `updateProfile({display_name})`：`auth.updateMe` → 更新 `user`。
  - `changePassword(body)`：`auth.changePassword`。
  - `logout()`：`auth.logout()`（catch 忽略）→ `setToken(null)` + `user=null` → 跳 `/login`。

## 5. 类型 `types/auth.ts`

```ts
interface User { id: number; username: string; email: string; display_name: string | null; status: string }
interface TokenResponse { access_token: string; token_type: string }
interface RegisterPayload { username: string; email: string; password: string; display_name?: string | null }
interface ApiError { status: number; code: string; message: string; details: Record<string, unknown> }
```

## 6. 视图

**`LoginView.vue`** — `el-tabs`：
- 登录：username + password，`el-form` rules；提交 `authStore.login` → 成功 `router.push("/")`；失败（401）就地红字"用户名或密码错误"。
- 注册：username(≥3) + email + password(≥6) + display_name(可选)，rules 对齐后端；提交 `authStore.register` → 成功切登录 tab + `ElMessage.success`；409 就地"用户名或邮箱已被占用"；403 "注册已关闭"。

**`ProfileView.vue`**：
- 只读显示 username / email / status。
- 改 display_name：`el-input` + 保存 → `updateProfile` → 成功提示。
- 改密码：old + new(≥6) `el-form` → `changePassword` → 成功提示。
- 登出按钮 → `authStore.logout()`。

## 7. 路由 `router/index.ts`

```
/login    LoginView      meta:{public:true}
/profile  ProfileView
/         redirect → /profile    （F2 改为 /projects）
```
`router.beforeEach`：
- 目标非 public 且 `!isAuthenticated` → `/login`。
- 已登录访问 `/login` → `/`。

## 8. 测试（Vitest + @vue/test-utils，mock api 层）

- `client.spec.ts`：请求拦截加 Bearer（有/无 token）；401 清 token + 跳转；错误信封归一化为 ApiError；静默路径不弹 ElMessage。
- `auth.store.spec.ts`：login 存 token+localStorage+填 user；register 不自动登录；logout 清空；isAuthenticated 反映 token。
- `LoginView.spec.ts`：渲染登录/注册 tab；登录提交调 store.login；登录失败显示错误文案；注册表单校验拦截非法输入（短用户名/非邮箱）。
- `ProfileView.spec.ts`：渲染用户信息；改 display_name 调 updateProfile；改密码调 changePassword；登出调 logout。
- `router.guard.spec.ts`：未登录访问 /profile → 重定向 /login；已登录访问 /login → 重定向 /。

## Definition of Done

- `npm install` 后 `npm run build`（含 `vue-tsc` 类型检查）通过，无 TS 错误。
- `npm run test`（Vitest）全绿。
- 手动：起后端（`uvicorn` + MySQL/Neo4j）+ `npm run dev`，注册 → 登录 → /profile 看资料 → 改 display_name → 改密码 → 登出，全流程经 dev proxy 走通。
- 刷新页面不掉登录（token 持久）；未登录访问受守卫保护。

## 下一子项目预告（不在本计划内）

- F2：项目列表（建/归档/恢复/purge）+ 成员管理（RBAC 按钮显隐）+ Schema 管理（含 SchemaForm）。复用 F1 的 client/store/守卫。

