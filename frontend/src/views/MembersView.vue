<template>
  <div>
    <div class="bar">
      <h3>成员</h3>
      <el-button v-if="proj.can('admin')" type="primary" @click="dialogVisible = true">添加成员</el-button>
    </div>
    <el-table :data="members" v-loading="loading">
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="display_name" label="显示名" />
      <el-table-column label="角色" width="160">
        <template #default="{ row }">
          <el-select
            v-if="proj.can('admin') && row.role !== 'owner'"
            :model-value="row.role" @change="(r) => onChangeRole(row, r)"
          >
            <el-option v-for="r in roles" :key="r" :label="r" :value="r" />
          </el-select>
          <span v-else>{{ row.role }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
            v-if="proj.can('admin') && row.role !== 'owner'"
            link type="danger" @click="onRemove(row)"
          >移除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <MemberFormDialog :visible="dialogVisible" @close="dialogVisible = false" @submit="onAdd" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { membersApi } from "@/api/members"
import { useProjectStore } from "@/stores/project"
import type { Member, Role } from "@/types/graph"
import MemberFormDialog from "@/components/MemberFormDialog.vue"

const route = useRoute()
const proj = useProjectStore()
const pid = computed(() => Number(route.params.pid))
const members = ref<Member[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const roles: Role[] = ["admin", "editor", "viewer"]

async function reload() {
  loading.value = true
  try {
    members.value = await membersApi.list(pid.value)
  } finally {
    loading.value = false
  }
}
onMounted(reload)

async function onAdd(body: { username?: string; email?: string; role: Role }) {
  await membersApi.add(pid.value, body)
  dialogVisible.value = false
  ElMessage.success("已添加")
  await reload()
}
async function onChangeRole(row: Member, role: Role) {
  await membersApi.changeRole(pid.value, row.user_id, role)
  ElMessage.success("角色已更新")
  await reload()
}
async function onRemove(row: Member) {
  await ElMessageBox.confirm(`移除成员「${row.username}」？`, "确认", { type: "warning" })
  await membersApi.remove(pid.value, row.user_id)
  ElMessage.success("已移除")
  await reload()
}
</script>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; }
</style>
