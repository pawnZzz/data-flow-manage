<template>
  <el-dialog :model-value="visible" title="设置父节点" @update:model-value="emit('close')">
    <el-select v-model="parentId" placeholder="选择父节点" filterable style="width: 100%">
      <el-option v-for="c in candidates" :key="c.id" :label="c.name" :value="c.id" />
    </el-select>
    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :disabled="!parentId" @click="onSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"

const props = defineProps<{ visible: boolean; candidates: { id: string; name: string }[] }>()
const emit = defineEmits<{ close: []; submit: [parentId: string] }>()

const parentId = ref("")
watch(() => props.visible, (v) => { if (v) parentId.value = "" })

function onSubmit() {
  if (parentId.value) emit("submit", parentId.value)
}

defineExpose({ setParentId: (id: string) => { parentId.value = id } })
</script>
