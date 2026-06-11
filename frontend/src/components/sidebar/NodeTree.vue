<template>
  <el-tree
    :data="treeData"
    :props="{ label: 'label', children: 'children' }"
    node-key="id"
    default-expand-all
    @node-click="(d: TreeNode) => emit('select', d.id)"
  />
</template>

<script setup lang="ts">
import { computed } from "vue"
import type { NodeResponse } from "@/types/graph"

const props = defineProps<{ nodes: NodeResponse[]; matchedIds: Set<string> | null }>()
const emit = defineEmits<{ select: [id: string] }>()

interface TreeNode { id: string; label: string; children: TreeNode[] }

const treeData = computed<TreeNode[]>(() => {
  const visible = props.matchedIds
    ? props.nodes.filter((n) => props.matchedIds!.has(n.id))
    : props.nodes
  const byId = new Map<string, TreeNode>()
  for (const n of visible) {
    const tag = n.priority ? ` [${n.priority}]` : ""
    const star = n.is_critical ? " ★" : ""
    byId.set(n.id, { id: n.id, label: `${n.name}${tag}${star}`, children: [] })
  }
  const roots: TreeNode[] = []
  for (const n of visible) {
    const node = byId.get(n.id)!
    const parent = n.parent_id ? byId.get(n.parent_id) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  return roots
})
</script>
