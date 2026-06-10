<template>
  <el-dialog :model-value="visible" :title="isEdit ? '编辑项目' : '新建项目'" @update:model-value="emit('close')">
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent>
      <el-form-item prop="name" label="名称">
        <el-input v-model="form.name" placeholder="项目名称" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :loading="busy" @click="onSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from "vue"
import { type FormInstance, type FormRules } from "element-plus"
import type { Project } from "@/types/graph"

const props = defineProps<{ visible: boolean; isEdit: boolean; project?: Project | null }>()
const emit = defineEmits<{ close: []; submit: [{ name: string; description: string | null }] }>()

const formRef = ref<FormInstance>()
const form = reactive({ name: "", description: "" })
const busy = ref(false)
const rules: FormRules = { name: [{ required: true, message: "请输入名称", trigger: "blur" }] }

watch(
  () => props.visible,
  (v) => {
    if (v) {
      form.name = props.project?.name ?? ""
      form.description = props.project?.description ?? ""
    }
  },
)

async function onSubmit() {
  if (!(await formRef.value?.validate().catch(() => false))) return
  busy.value = true
  try {
    emit("submit", { name: form.name, description: form.description || null })
  } finally {
    busy.value = false
  }
}
</script>
