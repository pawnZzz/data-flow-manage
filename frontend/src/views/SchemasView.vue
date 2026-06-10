<template>
  <div>
    <div class="bar">
      <h3>类型 Schema</h3>
      <el-button v-if="proj.can('editor')" type="primary" @click="openCreate">新建 Schema</el-button>
    </div>
    <el-table :data="schemas" v-loading="loading">
      <el-table-column prop="type_key" label="type_key" />
      <el-table-column prop="display_name" label="显示名" />
      <el-table-column label="字段数" width="100">
        <template #default="{ row }">{{ row.fields.length }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button v-if="proj.can('editor')" link @click="openEdit(row)">编辑</el-button>
          <el-button v-if="proj.can('admin')" link type="danger" @click="onRemove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <SchemaForm
      :visible="dialogVisible" :is-edit="editing !== null" :schema="editing"
      @close="dialogVisible = false" @submit="onSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { schemasApi } from "@/api/schemas"
import { useProjectStore } from "@/stores/project"
import type { NodeTypeSchema, SchemaField } from "@/types/graph"
import SchemaForm from "@/components/SchemaForm.vue"

const route = useRoute()
const proj = useProjectStore()
const pid = computed(() => Number(route.params.pid))
const schemas = ref<NodeTypeSchema[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref<NodeTypeSchema | null>(null)

async function reload() {
  loading.value = true
  try {
    schemas.value = await schemasApi.list(pid.value)
  } finally {
    loading.value = false
  }
}
onMounted(reload)

function openCreate() {
  editing.value = null
  dialogVisible.value = true
}
function openEdit(row: NodeTypeSchema) {
  editing.value = row
  dialogVisible.value = true
}
async function onSubmit(body: { type_key: string; display_name: string; fields: SchemaField[] }) {
  if (editing.value) {
    await schemasApi.update(pid.value, editing.value.type_key, { display_name: body.display_name, fields: body.fields })
  } else {
    await schemasApi.create(pid.value, body)
  }
  dialogVisible.value = false
  ElMessage.success("已保存")
  await reload()
}
async function onRemove(row: NodeTypeSchema) {
  await ElMessageBox.confirm(`删除 schema「${row.type_key}」？`, "确认", { type: "warning" })
  await schemasApi.remove(pid.value, row.type_key)
  ElMessage.success("已删除")
  await reload()
}
</script>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; }
</style>
