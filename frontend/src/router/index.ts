import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "login", component: () => import("@/views/LoginView.vue"), meta: { public: true } },
  { path: "/profile", name: "profile", component: () => import("@/views/ProfileView.vue") },
  { path: "/projects", name: "projects", component: () => import("@/views/ProjectListView.vue") },
  {
    path: "/projects/:pid",
    component: () => import("@/views/ProjectLayout.vue"),
    children: [
      { path: "", redirect: (to) => `/projects/${to.params.pid}/members` },
      { path: "members", name: "members", component: () => import("@/views/MembersView.vue") },
    ],
  },
  { path: "/", redirect: "/projects" },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthenticated) return { name: "login" }
  if (to.name === "login" && auth.isAuthenticated) return { path: "/" }
  return true
})

export default router
