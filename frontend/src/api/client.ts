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
