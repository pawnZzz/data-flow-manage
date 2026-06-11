<template>
  <div class="graph-view">
    <aside class="sidebar">
      <FilterBar :filters="store.filters" :nodes="store.sidebarNodes" @set-filter="store.setFilter" @clear="store.clearFilters" />
      <el-divider />
      <NodeTree :nodes="store.sidebarNodes" :matched-ids="store.matchedIds" @select="onSelect" />
    </aside>
    <section class="canvas-area">
      <div class="toolbar">
        <span v-if="store.subgraph">节点 {{ store.subgraph.stats.node_count }} · 边 {{ store.subgraph.stats.edge_count }}<span v-if="store.subgraph.stats.has_cycle"> · ⚠ 有环</span></span>
        <div class="toolbar-actions">
          <el-button v-if="proj.can('editor')" size="small" type="primary" @click="openCreateNode">新建节点</el-button>
          <el-button size="small" @click="onRelayout">重新布局</el-button>
        </div>
      </div>
      <el-empty v-if="store.subgraph && store.subgraph.nodes.length === 0" description="暂无节点" />
      <GraphCanvas
        v-else
        ref="canvas"
        :subgraph="store.subgraph"
        :matched-ids="store.matchedIds"
        :selected-id="store.selectedId"
        :saved-positions="savedPositions"
        :editable="proj.can('editor')"
        @select="onSelect"
        @node-moved="onNodeMoved"
        @edge-connected="onEdgeConnected"
        @node-contextmenu="(id: string, x: number, y: number) => openMenu('node', id, x, y)"
        @edge-contextmenu="(id: string, x: number, y: number) => openMenu('edge', id, x, y)"
      />
    </section>
    <NodeContextMenu
      :visible="menu.visible" :x="menu.x" :y="menu.y" :kind="menu.kind"
      @delete="onMenuDelete" @set-parent="onMenuSetParent" @clear-parent="onMenuClearParent" @close="menu.visible = false"
    />
    <CreateNodeDialog :visible="createVisible" :schemas="schemas" @close="createVisible = false" @submit="onCreateNode" />
    <SetParentDialog :visible="parentVisible" :candidates="parentCandidates" @close="parentVisible = false" @submit="onSetParent" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { useRoute } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { useGraphStore } from "@/stores/graph"
import { useProjectStore } from "@/stores/project"
import { useAuthStore } from "@/stores/auth"
import { schemasApi } from "@/api/schemas"
import { read, savePos, clear as clearPrefs } from "@/components/graph/viewPrefs"
import type { NodeTypeSchema, XYPos } from "@/types/graph"
import FilterBar from "@/components/sidebar/FilterBar.vue"
import NodeTree from "@/components/sidebar/NodeTree.vue"
import GraphCanvas from "@/components/graph/GraphCanvas.vue"
import CreateNodeDialog from "@/components/graph/CreateNodeDialog.vue"
import SetParentDialog from "@/components/graph/SetParentDialog.vue"
import NodeContextMenu from "@/components/graph/NodeContextMenu.vue"

const route = useRoute()
const store = useGraphStore()
const proj = useProjectStore()
const auth = useAuthStore()
const pid = computed(() => Number(route.params.pid))
const uid = computed(() => auth.user?.id ?? 0)
const canvas = ref<InstanceType<typeof GraphCanvas>>()
const savedPositions = ref<Record<string, XYPos>>({})

onMounted(async () => {
  savedPositions.value = read(pid.value, uid.value).positions
  await store.loadGraph(pid.value)
})

function onSelect(id: string) {
  store.select(id)
  canvas.value?.centerOn(id)
}
function onNodeMoved(id: string, xy: XYPos) {
  savePos(pid.value, uid.value, id, xy)
}
function onRelayout() {
  clearPrefs(pid.value, uid.value)
  savedPositions.value = {}
  canvas.value?.relayout()
}

const schemas = ref<NodeTypeSchema[]>([])
const createVisible = ref(false)
const parentVisible = ref(false)
const parentTargetId = ref("")
const menu = reactive({ visible: false, kind: "node" as "node" | "edge", id: "", x: 0, y: 0 })

const parentCandidates = computed(() =>
  store.sidebarNodes.filter((n) => n.id !== parentTargetId.value).map((n) => ({ id: n.id, name: n.name })),
)

async function openCreateNode() {
  schemas.value = await schemasApi.list(pid.value)
  createVisible.value = true
}
async function onCreateNode(body: { name: string; type: string }) {
  await store.createNode(body)
  createVisible.value = false
  ElMessage.success("节点已创建")
}
async function onEdgeConnected(sourceId: string, targetId: string) {
  const res = await store.createEdge({ source_id: sourceId, target_id: targetId })
  if (res.warnings.creates_cycle) ElMessage.warning("依赖已创建，但会形成环")
}
function openMenu(kind: "node" | "edge", id: string, x: number, y: number) {
  if (!proj.can("editor")) return // viewer 无编辑右键菜单
  Object.assign(menu, { visible: true, kind, id, x, y })
}
async function onMenuDelete() {
  const { id, kind } = menu
  menu.visible = false
  await ElMessageBox.confirm(kind === "node" ? "删除该节点及其关系？" : "删除该依赖边？", "确认", { type: "warning" })
  if (kind === "node") await store.deleteNode(id)
  else await store.deleteEdge(id)
  ElMessage.success("已删除")
}
function onMenuSetParent() {
  parentTargetId.value = menu.id
  menu.visible = false
  parentVisible.value = true
}
async function onSetParent(parentId: string) {
  await store.setParent(parentTargetId.value, parentId)
  parentVisible.value = false
  ElMessage.success("父节点已设置")
}
async function onMenuClearParent() {
  const id = menu.id
  menu.visible = false
  await store.clearParent(id)
  ElMessage.success("已解除父节点")
}
</script>

<style scoped>
.graph-view { display: flex; height: calc(100vh - 120px); }
.sidebar { width: 240px; padding: 12px; border-right: 1px solid #eee; overflow: auto; }
.canvas-area { flex: 1; display: flex; flex-direction: column; }
.toolbar { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid #eee; }
.toolbar-actions { display: flex; gap: 8px; }
</style>
