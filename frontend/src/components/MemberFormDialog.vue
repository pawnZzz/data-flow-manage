<template>
  <el-dialog :model-value="visible" title="添加成员" @update:model-value="emit('close')">
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent>
      <el-form-item prop="identifier" label="用户名/邮箱">
        <el-input v-model="form.identifier" placeholder="用户名或邮箱" />
      </el-form-item>
      <el-form-item prop="role" label="角色">
        <el-select v-model="form.role">
          <el-option v-for="r in roles" :key="r" :label="r" :value="r" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" @click="onSubmit">添加</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from "vue"
import { type FormInstance, type FormRules } from "element-plus"
import type { Role } from "@/types/graph"

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: []; submit: [{ username?: string; email?: string; role: Role }] }>()

const roles: Role[] = ["admin", "editor", "viewer"]
const formRef = ref<FormInstance>()
const form = reactive({ identifier: "", role: "viewer" as Role })
const rules: FormRules = {
  identifier: [{ required: true, message: "请输入用户名或邮箱", trigger: "blur" }],
}

watch(() => props.visible, (v) => { if (v) { form.identifier = ""; form.role = "viewer" } })

async function onSubmit() {
  if (!(await formRef.value?.validate().catch(() => false))) return
  const id = form.identifier.trim()
  const body = id.includes("@") ? { email: id, role: form.role } : { username: id, role: form.role }
  emit("submit", body)
}
</script>
