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
