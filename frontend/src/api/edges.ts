import { http } from "./client"
import type { GraphEdge } from "@/types/graph"

export interface CreateEdgeResponse {
  edge: GraphEdge
  warnings: { creates_cycle: boolean }
}

export const edgesApi = {
  create: (pid: number, body: { source_id: string; target_id: string; edge_type?: string }) =>
    http.post(`/projects/${pid}/edges`, body) as unknown as Promise<CreateEdgeResponse>,
  remove: (pid: number, eid: string) =>
    http.delete(`/projects/${pid}/edges/${eid}`) as unknown as Promise<void>,
}
