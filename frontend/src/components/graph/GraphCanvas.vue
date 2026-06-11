<template>
  <div ref="el" class="x6-canvas" />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from "vue"
import type { Subgraph, XYPos } from "@/types/graph"
import { GraphController } from "./graphController"

const props = defineProps<{
  subgraph: Subgraph | null
  matchedIds: Set<string> | null
  selectedId: string | null
  savedPositions: Record<string, XYPos>
}>()
const emit = defineEmits<{ select: [id: string]; nodeMoved: [id: string, xy: XYPos] }>()

const el = ref<HTMLElement>()
const controller = new GraphController()

async function render() {
  if (!props.subgraph) return
  controller.setData(props.subgraph.nodes, props.subgraph.edges)
  if (Object.keys(props.savedPositions).length > 0) controller.applyPositions(props.savedPositions)
  else await controller.runLayout()
  controller.applyMatch(props.matchedIds)
  controller.highlightSelected(props.selectedId)
}

onMounted(async () => {
  controller.init(el.value!)
  controller.onNodeClick((id) => emit("select", id))
  controller.onNodeMoved((id, xy) => emit("nodeMoved", id, xy))
  await render()
})
onBeforeUnmount(() => controller.dispose())

watch(() => props.subgraph, render)
watch(() => props.matchedIds, (ids) => controller.applyMatch(ids))
watch(() => props.selectedId, (id) => controller.highlightSelected(id))

defineExpose({
  relayout: () => controller.runLayout(),
  centerOn: (id: string) => controller.centerOn(id),
})
</script>

<style scoped>
.x6-canvas { width: 100%; height: 100%; min-height: 70vh; }
</style>
