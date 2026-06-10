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
    await authApi.register(payload)
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
