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
        <el-button size="small" @click="onRelayout">重新布局</el-button>
      </div>
      <el-empty v-if="store.subgraph && store.subgraph.nodes.length === 0" description="暂无节点" />
      <GraphCanvas
        v-else
        ref="canvas"
        :subgraph="store.subgraph"
        :matched-ids="store.matchedIds"
        :selected-id="store.selectedId"
        :saved-positions="savedPositions"
        :editable="false"
        @select="onSelect"
        @node-moved="onNodeMoved"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { useGraphStore } from "@/stores/graph"
import { useAuthStore } from "@/stores/auth"
import { read, savePos, clear as clearPrefs } from "@/components/graph/viewPrefs"
import type { XYPos } from "@/types/graph"
import FilterBar from "@/components/sidebar/FilterBar.vue"
import NodeTree from "@/components/sidebar/NodeTree.vue"
import GraphCanvas from "@/components/graph/GraphCanvas.vue"

const route = useRoute()
const store = useGraphStore()
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
</script>

<style scoped>
.graph-view { display: flex; height: calc(100vh - 120px); }
.sidebar { width: 240px; padding: 12px; border-right: 1px solid #eee; overflow: auto; }
.canvas-area { flex: 1; display: flex; flex-direction: column; }
.toolbar { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid #eee; }
</style>
