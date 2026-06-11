<template>
  <div class="layout" v-if="proj.current">
    <header class="topbar">
      <span class="name">{{ proj.current.name }}</span>
      <el-tag size="small">{{ proj.current.status }}</el-tag>
      <el-button class="back" link @click="router.push('/projects')">← 项目列表</el-button>
    </header>
    <div class="body">
      <nav class="side">
        <router-link :to="`/projects/${pid}`">图谱</router-link>
        <router-link :to="`/projects/${pid}/members`">成员</router-link>
        <router-link :to="`/projects/${pid}/schemas`">类型 Schema</router-link>
      </nav>
      <main class="content"><router-view /></main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useProjectStore } from "@/stores/project"

const route = useRoute()
const router = useRouter()
const proj = useProjectStore()
const pid = computed(() => Number(route.params.pid))

async function loadProject(id: number) {
  try {
    await proj.load(id)
  } catch {
    router.replace("/projects")
  }
}

watch(pid, (id) => { if (id) loadProject(id) }, { immediate: true })
</script>

<style scoped>
.topbar { display: flex; align-items: center; gap: 12px; padding: 12px 20px; border-bottom: 1px solid #eee; }
.name { font-weight: 600; font-size: 16px; }
.back { margin-left: auto; }
.body { display: flex; }
.side { width: 160px; display: flex; flex-direction: column; padding: 16px; gap: 8px; border-right: 1px solid #eee; min-height: 70vh; }
.content { flex: 1; padding: 20px; }
</style>
