import { http } from "./client"
import type { NodeFilters, NodeResponse } from "@/types/graph"

export const nodesApi = {
  list: (pid: number, filters: NodeFilters = {}) =>
    http.get(`/projects/${pid}/nodes`, { params: filters }) as unknown as Promise<NodeResponse[]>,
  create: (pid: number, body: { name: string; type: string }) =>
    http.post(`/projects/${pid}/nodes`, body) as unknown as Promise<NodeResponse>,
  remove: (pid: number, nid: string) =>
    http.delete(`/projects/${pid}/nodes/${nid}`) as unknown as Promise<void>,
  setParent: (pid: number, nid: string, parent_id: string) =>
    http.post(`/projects/${pid}/nodes/${nid}/parent`, { parent_id }) as unknown as Promise<void>,
  clearParent: (pid: number, nid: string) =>
    http.delete(`/projects/${pid}/nodes/${nid}/parent`) as unknown as Promise<void>,
}
