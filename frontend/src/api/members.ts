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
