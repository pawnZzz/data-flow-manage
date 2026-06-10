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
