export type Role = "owner" | "admin" | "editor" | "viewer"

const ROLE_LEVEL: Record<Role, number> = { owner: 4, admin: 3, editor: 2, viewer: 1 }

export function roleAtLeast(role: Role | null | undefined, min: Role): boolean {
  if (!role) return false
  return ROLE_LEVEL[role] >= ROLE_LEVEL[min]
}

export interface Project {
  id: number
  name: string
  description: string | null
  status: string
  created_by: number
  my_role: Role
}

export interface Member {
  user_id: number
  username: string
  display_name: string | null
  role: Role
}

export type FieldType = "string" | "number" | "url" | "enum" | "bool"

export interface SchemaField {
  name: string
  label: string
  type: FieldType
  required: boolean
  options?: string[] | null
  default?: unknown
}

export interface NodeTypeSchema {
  id: string
  type_key: string
  display_name: string
  fields: SchemaField[]
  created_at: string
  updated_at: string
}

export interface PurgeResult {
  deleted_nodes: number
  deleted_schemas: number
}

export interface GraphEdge {
  id: string
  project_id: number
  source_id: string
  target_id: string
  edge_type: string
  description: string | null
  is_required: boolean
  strength: string
  ext_props: Record<string, unknown>
  created_at: string
  created_by: number
}

export interface GraphSubgraphNode {
  id: string
  name: string
  type: string
  priority: string | null
  is_critical: boolean
  parent_id: string | null
}

export interface GraphStats {
  node_count: number
  edge_count: number
  has_cycle: boolean
}

export interface Subgraph {
  nodes: GraphSubgraphNode[]
  edges: GraphEdge[]
  stats: GraphStats
}

export interface XYPos {
  x: number
  y: number
}

export interface NodeResponse {
  id: string
  project_id: number
  name: string
  type: string
  description: string | null
  owner: string | null
  department: string | null
  system: string | null
  priority: string | null
  tags: string[]
  ext_props: Record<string, unknown>
  is_critical: boolean
  parent_id: string | null
  children_count: number
  upstream_count: number
  downstream_count: number
}

export interface NodeFilters {
  type?: string
  department?: string
  system?: string
  priority?: string
  tag?: string
  name?: string
}
