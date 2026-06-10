import { http } from "./client"
import type { NodeTypeSchema, SchemaField } from "@/types/graph"

export const schemasApi = {
  list: (pid: number) => http.get(`/projects/${pid}/schemas`) as unknown as Promise<NodeTypeSchema[]>,
  create: (pid: number, body: { type_key: string; display_name: string; fields: SchemaField[] }) =>
    http.post(`/projects/${pid}/schemas`, body) as unknown as Promise<NodeTypeSchema>,
  update: (pid: number, typeKey: string, body: { display_name?: string; fields?: SchemaField[] }) =>
    http.put(`/projects/${pid}/schemas/${typeKey}`, body) as unknown as Promise<NodeTypeSchema>,
  remove: (pid: number, typeKey: string) =>
    http.delete(`/projects/${pid}/schemas/${typeKey}`) as unknown as Promise<void>,
}
