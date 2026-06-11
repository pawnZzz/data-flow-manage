import type { XYPos } from "@/types/graph"

export interface Viewport {
  zoom: number
  tx: number
  ty: number
}
export interface GraphPrefs {
  positions: Record<string, XYPos>
  viewport?: Viewport
}

function key(pid: number, uid: number): string {
  return `graph:${pid}:${uid}`
}

export function read(pid: number, uid: number): GraphPrefs {
  const raw = localStorage.getItem(key(pid, uid))
  if (!raw) return { positions: {} }
  try {
    const parsed = JSON.parse(raw) as GraphPrefs
    return { positions: parsed.positions ?? {}, viewport: parsed.viewport }
  } catch {
    return { positions: {} }
  }
}

export function savePos(pid: number, uid: number, id: string, xy: XYPos): void {
  const prefs = read(pid, uid)
  prefs.positions[id] = xy
  localStorage.setItem(key(pid, uid), JSON.stringify(prefs))
}

export function saveViewport(pid: number, uid: number, vp: Viewport): void {
  const prefs = read(pid, uid)
  prefs.viewport = vp
  localStorage.setItem(key(pid, uid), JSON.stringify(prefs))
}

export function clear(pid: number, uid: number): void {
  localStorage.removeItem(key(pid, uid))
}
