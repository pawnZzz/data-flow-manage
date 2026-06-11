import type { GraphSubgraphNode, XYPos } from "@/types/graph"

const PALETTE = ["#5B8FF9", "#5AD8A6", "#5D7092", "#F6BD16", "#E8684A", "#6DC8EC", "#9270CA", "#FF9D4D"]

export function colorForType(type: string): string {
  let h = 0
  for (let i = 0; i < type.length; i++) h = (h * 31 + type.charCodeAt(i)) >>> 0
  return PALETTE[h % PALETTE.length]
}

export interface XNode {
  id: string
  x: number
  y: number
  width: number
  height: number
  label: string
  attrs: { body: { fill: string; stroke: string; strokeWidth: number } }
}

export function toXNode(n: GraphSubgraphNode, pos: XYPos = { x: 0, y: 0 }): XNode {
  const label = n.priority ? `${n.name} [${n.priority}]` : n.name
  return {
    id: n.id,
    x: pos.x,
    y: pos.y,
    width: 160,
    height: 40,
    label,
    attrs: {
      body: {
        fill: colorForType(n.type),
        stroke: n.is_critical ? "#F5222D" : "#C2C8D5",
        strokeWidth: n.is_critical ? 3 : 1,
      },
    },
  }
}
