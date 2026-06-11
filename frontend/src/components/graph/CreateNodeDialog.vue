<template>
  <el-dialog :model-value="visible" title="新建节点" @update:model-value="emit('close')">
    <el-alert v-if="schemas.length === 0" type="warning" :closable="false" title="请先在 Schema 管理中创建类型" />
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent>
      <el-form-item prop="name" label="名称">
        <el-input v-model="form.name" placeholder="节点名称" />
      </el-form-item>
      <el-form-item prop="type" label="类型">
        <el-select v-model="form.type" placeholder="选择类型">
          <el-option v-for="s in schemas" :key="s.type_key" :label="s.display_name" :value="s.type_key" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :disabled="schemas.length === 0" @click="onSubmit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from "vue"
import { type FormInstance, type FormRules } from "element-plus"
import type { NodeTypeSchema } from "@/types/graph"

const props = defineProps<{ visible: boolean; schemas: NodeTypeSchema[] }>()
const emit = defineEmits<{ close: []; submit: [{ name: string; type: string }] }>()

const formRef = ref<FormInstance>()
const form = reactive({ name: "", type: "" })
const rules: FormRules = {
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  type: [{ required: true, message: "请选择类型", trigger: "change" }],
}

watch(() => props.visible, (v) => { if (v) { form.name = ""; form.type = "" } })

async function onSubmit() {
  await formRef.value?.validate().catch(() => false)
  if (!form.name || !form.type) return
  emit("submit", { name: form.name, type: form.type })
}

defineExpose({ form })
</script>
