import { computed, ref } from "vue"
import { defineStore } from "pinia"
import { projectsApi } from "@/api/projects"
import { roleAtLeast, type Project, type Role } from "@/types/graph"

export const useProjectStore = defineStore("project", () => {
  const current = ref<Project | null>(null)

  const myRole = computed<Role | null>(() => current.value?.my_role ?? null)

  function can(min: Role): boolean {
    return roleAtLeast(myRole.value, min)
  }

  async function load(pid: number) {
    current.value = await projectsApi.get(pid)
  }

  function clear() {
    current.value = null
  }

  return { current, myRole, can, load, clear }
})
