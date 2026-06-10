export interface User {
  id: number
  username: string
  email: string
  display_name: string | null
  status: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
  display_name?: string | null
}

export interface ApiError {
  status: number
  code: string
  message: string
  details: Record<string, unknown>
}
