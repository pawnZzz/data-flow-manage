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
