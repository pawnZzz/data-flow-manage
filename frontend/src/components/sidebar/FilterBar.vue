<template>
  <div class="filter-bar">
    <el-input :model-value="filters.name" placeholder="搜索名称" clearable @update:model-value="(v: string) => set('name', v)" />
    <el-select :model-value="filters.type" placeholder="类型" clearable @update:model-value="(v: string) => set('type', v)">
      <el-option v-for="t in types" :key="t" :label="t" :value="t" />
    </el-select>
    <el-select :model-value="filters.priority" placeholder="优先级" clearable @update:model-value="(v: string) => set('priority', v)">
      <el-option v-for="p in priorities" :key="p" :label="p" :value="p" />
    </el-select>
    <el-input :model-value="filters.department" placeholder="部门" clearable @update:model-value="(v: string) => set('department', v)" />
    <el-input :model-value="filters.system" placeholder="系统" clearable @update:model-value="(v: string) => set('system', v)" />
    <el-input :model-value="filters.tag" placeholder="标签" clearable @update:model-value="(v: string) => set('tag', v)" />
    <el-button link @click="emit('clear')">清空</el-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import type { NodeFilters, NodeResponse } from "@/types/graph"

const props = defineProps<{ filters: NodeFilters; nodes: NodeResponse[] }>()
const emit = defineEmits<{ setFilter: [Partial<NodeFilters>]; clear: [] }>()

const priorities = ["P0", "P1", "P2", "P3", "P4", "P5"]
const types = computed(() => [...new Set(props.nodes.map((n) => n.type))])

function set(key: keyof NodeFilters, value: string) {
  emit("setFilter", { [key]: value || undefined })
}
</script>

<style scoped>
.filter-bar { display: flex; flex-direction: column; gap: 8px; }
</style>
