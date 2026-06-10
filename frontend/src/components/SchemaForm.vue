<template>
  <el-dialog :model-value="visible" :title="isEdit ? '编辑 Schema' : '新建 Schema'" width="720" @update:model-value="emit('close')">
    <el-form @submit.prevent>
      <el-form-item label="type_key">
        <el-input v-model="typeKey" :disabled="isEdit" placeholder="如 data_task" />
      </el-form-item>
      <el-form-item label="显示名">
        <el-input v-model="displayName" placeholder="如 数据任务" />
      </el-form-item>
    </el-form>

    <el-divider>字段</el-divider>
    <div v-for="(f, i) in fields" :key="i" class="field-row">
      <el-input v-model="f.name" placeholder="name" style="width: 120px" />
      <el-input v-model="f.label" placeholder="label" style="width: 120px" />
      <el-select v-model="f.type" style="width: 110px">
        <el-option v-for="t in fieldTypes" :key="t" :label="t" :value="t" />
      </el-select>
      <el-switch v-model="f.required" active-text="必填" />
      <el-input v-if="f.type === 'enum'" v-model="f.optionsText" placeholder="选项,逗号分隔" style="width: 180px" />
      <el-button link type="danger" @click="removeField(i)">删除</el-button>
    </div>
    <el-button @click="addField">添加字段</el-button>

    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" @click="onSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from "vue"
import { ElMessage } from "element-plus"
import type { FieldType, NodeTypeSchema, SchemaField } from "@/types/graph"

interface FieldRow { name: string; label: string; type: FieldType; required: boolean; optionsText: string }

const props = defineProps<{ visible: boolean; isEdit: boolean; schema?: NodeTypeSchema | null }>()
const emit = defineEmits<{ close: []; submit: [{ type_key: string; display_name: string; fields: SchemaField[] }] }>()

const fieldTypes: FieldType[] = ["string", "number", "url", "enum", "bool"]
const typeKey = ref("")
const displayName = ref("")
const fields = reactive<FieldRow[]>([])

watch(() => props.visible, (v) => {
  if (!v) return
  typeKey.value = props.schema?.type_key ?? ""
  displayName.value = props.schema?.display_name ?? ""
  fields.splice(0, fields.length,
    ...(props.schema?.fields ?? []).map((f) => ({
      name: f.name, label: f.label, type: f.type, required: f.required,
      optionsText: (f.options ?? []).join(","),
    })),
  )
}, { immediate: true })

function addField() {
  fields.push({ name: "", label: "", type: "string", required: false, optionsText: "" })
}
function removeField(i: number) {
  fields.splice(i, 1)
}

function onSubmit() {
  if (!props.isEdit && !typeKey.value.trim()) return ElMessage.warning("请输入 type_key")
  if (!displayName.value.trim()) return ElMessage.warning("请输入显示名")
  const names = new Set<string>()
  const out: SchemaField[] = []
  for (const f of fields) {
    const fname = f.name.trim()
    if (!fname) return ElMessage.warning("字段 name 不能为空")
    if (names.has(fname)) return ElMessage.warning(`字段 name 重复: ${fname}`)
    names.add(fname)
    let options: string[] | null = null
    if (f.type === "enum") {
      options = f.optionsText.split(",").map((s) => s.trim()).filter(Boolean)
      if (options.length === 0) return ElMessage.warning(`enum 字段 ${fname} 需至少一个选项`)
    }
    out.push({ name: fname, label: f.label.trim() || fname, type: f.type, required: f.required, options })
  }
  emit("submit", { type_key: typeKey.value.trim(), display_name: displayName.value.trim(), fields: out })
}
</script>

<style scoped>
.field-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
</style>
