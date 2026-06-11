<template>
  <ul v-if="visible" class="ctx-menu" :style="{ left: x + 'px', top: y + 'px' }" @click.stop>
    <template v-if="kind === 'node'">
      <li @click="emit('setParent')">设父节点</li>
      <li @click="emit('clearParent')">解除父</li>
      <li class="danger" @click="emit('delete')">删除节点</li>
    </template>
    <template v-else>
      <li class="danger" @click="emit('delete')">删除边</li>
    </template>
  </ul>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue"

const props = defineProps<{ visible: boolean; x: number; y: number; kind: "node" | "edge" }>()
const emit = defineEmits<{ delete: []; setParent: []; clearParent: []; close: [] }>()

function onDocClick() {
  if (props.visible) emit("close")
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape" && props.visible) emit("close")
}
onMounted(() => {
  document.addEventListener("click", onDocClick)
  document.addEventListener("keydown", onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick)
  document.removeEventListener("keydown", onKey)
})
</script>

<style scoped>
.ctx-menu { position: fixed; z-index: 3000; background: #fff; border: 1px solid #e4e7ed; border-radius: 4px; box-shadow: 0 2px 12px rgba(0,0,0,.1); padding: 4px 0; min-width: 120px; list-style: none; margin: 0; }
.ctx-menu li { padding: 6px 16px; cursor: pointer; font-size: 14px; }
.ctx-menu li:hover { background: #f5f7fa; }
.ctx-menu li.danger { color: #f56c6c; }
</style>
