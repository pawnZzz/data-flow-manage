import { Graph } from "@antv/x6"
import type { GraphEdge, GraphSubgraphNode, XYPos } from "@/types/graph"
import { toXNode } from "./nodeShapes"
import { dagre } from "./layout"

export class GraphController {
  private graph: Graph | null = null
  private nodes: GraphSubgraphNode[] = []
  private edges: GraphEdge[] = []
  private editable = false

  init(container: HTMLElement): void {
    this.graph = new Graph({
      container,
      autoResize: true,
      panning: true,
      mousewheel: { enabled: true },
      interacting: { nodeMovable: true },
      // Connecting options are read live at interaction time, so we gate both
      // the start (validateMagnet) and the completion (validateConnection) of a
      // node→node edge on `this.editable`. The node body is made a magnet in
      // setData; `allowNode` lets an edge target a node body (no ports needed).
      connecting: {
        snap: true,
        allowBlank: false,
        allowLoop: false,
        allowMulti: false,
        allowNode: true,
        router: "normal",
        validateMagnet: () => this.editable,
        validateConnection: () => this.editable,
      },
    })
  }

  setData(nodes: GraphSubgraphNode[], edges: GraphEdge[]): void {
    this.nodes = nodes
    this.edges = edges
    if (!this.graph) return
    this.graph.fromJSON({
      nodes: nodes.map((n) => {
        const x = toXNode(n)
        return {
          id: x.id,
          x: x.x,
          y: x.y,
          width: x.width,
          height: x.height,
          // X6 v3 renders node text via the `label` selector; top-level `label`
          // is not auto-mapped, so set the text through attrs.label.text.
          // `body.magnet` makes the body a connection source; validateMagnet
          // gates whether dragging an edge actually starts (editable only).
          attrs: { ...x.attrs, body: { ...x.attrs.body, magnet: true }, label: { text: x.label } },
        }
      }),
      edges: edges.map((e) => ({ id: e.id, source: e.source_id, target: e.target_id })),
    })
  }

  applyPositions(pos: Record<string, XYPos>): void {
    if (!this.graph) return
    for (const [id, p] of Object.entries(pos)) {
      const cell = this.graph.getCellById(id)
      if (cell?.isNode()) cell.position(p.x, p.y)
    }
  }

  async runLayout(): Promise<Record<string, XYPos>> {
    const pos = await dagre(this.nodes, this.edges)
    this.applyPositions(pos)
    return pos
  }

  highlightSelected(id: string | null): void {
    if (!this.graph) return
    this.graph.getNodes().forEach((node) => {
      node.attr("body/shadowBlur", node.id === id ? 12 : 0)
    })
  }

  applyMatch(ids: Set<string> | null): void {
    if (!this.graph) return
    this.graph.getNodes().forEach((node) => {
      const dim = ids !== null && !ids.has(node.id)
      node.attr("body/opacity", dim ? 0.25 : 1)
    })
  }

  centerOn(id: string): void {
    const cell = this.graph?.getCellById(id)
    if (cell?.isNode()) this.graph?.centerCell(cell)
  }

  onNodeMoved(cb: (id: string, xy: XYPos) => void): void {
    this.graph?.on("node:moved", ({ node }) => {
      const p = node.position()
      cb(node.id, { x: p.x, y: p.y })
    })
  }

  onNodeClick(cb: (id: string) => void): void {
    this.graph?.on("node:click", ({ node }) => cb(node.id))
  }

  setEditable(on: boolean): void {
    this.editable = on
  }

  onEdgeConnected(cb: (sourceId: string, targetId: string, edgeId: string) => void): void {
    this.graph?.on("edge:connected", ({ edge }) => {
      const s = edge.getSourceCellId()
      const t = edge.getTargetCellId()
      if (s && t) cb(s, t, edge.id)
    })
  }

  removeEdgeCell(edgeId: string): void {
    const cell = this.graph?.getCellById(edgeId)
    if (cell?.isEdge()) cell.remove()
  }

  onNodeContextmenu(cb: (id: string, x: number, y: number) => void): void {
    this.graph?.on("node:contextmenu", ({ node, e }) => cb(node.id, e.clientX, e.clientY))
  }

  onEdgeContextmenu(cb: (id: string, x: number, y: number) => void): void {
    this.graph?.on("edge:contextmenu", ({ edge, e }) => cb(edge.id, e.clientX, e.clientY))
  }

  dispose(): void {
    this.graph?.dispose()
    this.graph = null
  }
}
