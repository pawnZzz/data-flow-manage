<template>
  <div class="list-wrap">
    <div class="bar">
      <h2>我的项目</h2>
      <div>
        <el-switch v-model="showArchived" active-text="显示归档" @change="reload" />
        <el-button type="primary" @click="openCreate">新建项目</el-button>
      </div>
    </div>
    <el-table :data="projects" v-loading="loading">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="my_role" label="我的角色" width="100" />
      <el-table-column label="操作" width="320">
        <template #default="{ row }">
          <el-button link type="primary" @click="enter(row)">进入</el-button>
          <el-button v-if="roleAtLeast(row.my_role, 'admin')" link @click="openEdit(row)">改名</el-button>
          <el-button v-if="row.status === 'active' && roleAtLeast(row.my_role, 'owner')" link type="warning" @click="onArchive(row)">归档</el-button>
          <el-button v-if="row.status === 'archived' && roleAtLeast(row.my_role, 'owner')" link @click="onUnarchive(row)">恢复</el-button>
          <el-button v-if="row.status === 'archived' && roleAtLeast(row.my_role, 'owner')" link type="danger" @click="onPurge(row)">永久删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <ProjectFormDialog
      :visible="dialogVisible" :is-edit="editing !== null" :project="editing"
      @close="dialogVisible = false" @submit="onDialogSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { projectsApi } from "@/api/projects"
import { roleAtLeast, type Project } from "@/types/graph"
import ProjectFormDialog from "@/components/ProjectFormDialog.vue"

const router = useRouter()
const projects = ref<Project[]>([])
const loading = ref(false)
const showArchived = ref(false)
const dialogVisible = ref(false)
const editing = ref<Project | null>(null)

async function reload() {
  loading.value = true
  try {
    projects.value = await projectsApi.list(showArchived.value)
  } finally {
    loading.value = false
  }
}
onMounted(reload)

function enter(row: Project) {
  router.push(`/projects/${row.id}`)
}
function openCreate() {
  editing.value = null
  dialogVisible.value = true
}
function openEdit(row: Project) {
  editing.value = row
  dialogVisible.value = true
}
async function onDialogSubmit(body: { name: string; description: string | null }) {
  if (editing.value) await projectsApi.update(editing.value.id, body)
  else await projectsApi.create(body)
  dialogVisible.value = false
  ElMessage.success("已保存")
  await reload()
}
async function onArchive(row: Project) {
  await ElMessageBox.confirm(`归档项目「${row.name}」？归档后不可写。`, "确认", { type: "warning" })
  await projectsApi.archive(row.id)
  ElMessage.success("已归档")
  await reload()
}
async function onUnarchive(row: Project) {
  await projectsApi.unarchive(row.id)
  ElMessage.success("已恢复")
  await reload()
}
async function onPurge(row: Project) {
  const { value } = await ElMessageBox.prompt(
    `永久删除「${row.name}」不可恢复。请输入项目名以确认：`, "危险操作",
    { type: "error", inputValidator: (v) => v?.trim() === row.name || "名称不匹配" },
  )
  if (value?.trim() !== row.name) return
  const res = await projectsApi.purge(row.id)
  ElMessage.success(`已删除：${res.deleted_nodes} 节点 / ${res.deleted_schemas} schema`)
  await reload()
}
</script>

<style scoped>
.list-wrap { max-width: 960px; margin: 32px auto; }
.bar { display: flex; justify-content: space-between; align-items: center; }
</style>
