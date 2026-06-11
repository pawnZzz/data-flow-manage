import { http } from "./client"
import type { Subgraph } from "@/types/graph"

export const graphApi = {
  getSubgraph: (pid: number, params: { center?: string; depth?: number; direction?: string } = {}) =>
    http.get(`/projects/${pid}/graph`, { params }) as unknown as Promise<Subgraph>,
}
