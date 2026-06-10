<template>
  <div class="profile-wrap" v-if="auth.user">
    <el-card>
      <template #header>
        <span>个人设置</span>
        <el-button class="logout-btn" link type="danger" @click="onLogout">登出</el-button>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户名">{{ auth.user.username }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ auth.user.email }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ auth.user.status }}</el-descriptions-item>
      </el-descriptions>

      <el-divider>修改显示名</el-divider>
      <el-input v-model="displayName" placeholder="显示名" />
      <el-button type="primary" :loading="busy" @click="onSaveName">保存</el-button>

      <el-divider>修改密码</el-divider>
      <el-form ref="pwForm" :model="pw" :rules="pwRules" @submit.prevent>
        <el-form-item prop="old_password">
          <el-input v-model="pw.old_password" type="password" placeholder="原密码" show-password />
        </el-form-item>
        <el-form-item prop="new_password">
          <el-input v-model="pw.new_password" type="password" placeholder="新密码（≥6）" show-password />
        </el-form-item>
        <el-button type="primary" :loading="busy" @click="onChangePw">修改密码</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { ElMessage, type FormInstance, type FormRules } from "element-plus"
import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()
const router = useRouter()
const busy = ref(false)
const displayName = ref("")
const pwForm = ref<FormInstance>()
const pw = reactive({ old_password: "", new_password: "" })
const pwRules: FormRules = {
  old_password: [{ required: true, message: "请输入原密码", trigger: "blur" }],
  new_password: [{ required: true, min: 6, message: "新密码至少 6 位", trigger: "blur" }],
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  displayName.value = auth.user?.display_name ?? ""
})

async function onSaveName() {
  busy.value = true
  try {
    await auth.updateProfile(displayName.value || null)
    ElMessage.success("已保存")
  } finally {
    busy.value = false
  }
}

async function onChangePw() {
  if (!(await pwForm.value?.validate().catch(() => false))) return
  busy.value = true
  try {
    await auth.changePassword(pw.old_password, pw.new_password)
    ElMessage.success("密码已修改")
    pw.old_password = ""
    pw.new_password = ""
  } finally {
    busy.value = false
  }
}

async function onLogout() {
  await auth.logout()
  router.push("/login")
}
</script>

<style scoped>
.profile-wrap { max-width: 560px; margin: 40px auto; }
.logout-btn { float: right; }
</style>
