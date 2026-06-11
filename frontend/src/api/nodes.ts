import { http } from "./client"
import type { NodeFilters, NodeResponse } from "@/types/graph"

export const nodesApi = {
  list: (pid: number, filters: NodeFilters = {}) =>
    http.get(`/projects/${pid}/nodes`, { params: filters }) as unknown as Promise<NodeResponse[]>,
}
