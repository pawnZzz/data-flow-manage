import { DagreLayout } from "@antv/layout"
import type { GraphEdge, GraphSubgraphNode, XYPos } from "@/types/graph"

export async function dagre(
  nodes: GraphSubgraphNode[],
  edges: GraphEdge[],
): Promise<Record<string, XYPos>> {
  if (nodes.length === 0) return {}
  const layout = new DagreLayout({
    rankdir: "TB",
    nodesep: 40,
    ranksep: 60,
  })
  const data = {
    nodes: nodes.map((n) => ({ id: n.id, data: {} })),
    edges: edges.map((e) => ({ id: e.id, source: e.source_id, target: e.target_id, data: {} })),
  }
  await layout.execute(data)
  const pos: Record<string, XYPos> = {}
  layout.forEachNode((n) => {
    pos[String(n.id)] = { x: n.x, y: n.y }
  })
  return pos
}
