<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login">
          <el-form ref="loginForm" :model="loginData" :rules="loginRules" @submit.prevent>
            <el-form-item prop="username">
              <el-input v-model="loginData.username" placeholder="用户名" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginData.password" type="password" placeholder="密码" show-password />
            </el-form-item>
            <el-alert v-if="loginError" :title="loginError" type="error" :closable="false" />
            <el-button type="primary" :loading="busy" @click="onLogin">登录</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form ref="regForm" :model="regData" :rules="regRules" @submit.prevent>
            <el-form-item prop="username">
              <el-input v-model="regData.username" placeholder="用户名（≥3）" />
            </el-form-item>
            <el-form-item prop="email">
              <el-input v-model="regData.email" placeholder="邮箱" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="regData.password" type="password" placeholder="密码（≥6）" show-password />
            </el-form-item>
            <el-form-item prop="display_name">
              <el-input v-model="regData.display_name" placeholder="显示名（可选）" />
            </el-form-item>
            <el-alert v-if="regError" :title="regError" type="error" :closable="false" />
            <el-button type="primary" :loading="busy" @click="onRegister">注册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { ElMessage, type FormInstance, type FormRules } from "element-plus"
import { useAuthStore } from "@/stores/auth"
import type { ApiError } from "@/types/auth"

const router = useRouter()
const auth = useAuthStore()
const tab = ref("login")
const busy = ref(false)

const loginForm = ref<FormInstance>()
const regForm = ref<FormInstance>()
const loginData = reactive({ username: "", password: "" })
const regData = reactive({ username: "", email: "", password: "", display_name: "" })
const loginError = ref("")
const regError = ref("")

const loginRules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
}
const regRules: FormRules = {
  username: [{ required: true, min: 3, message: "用户名至少 3 位", trigger: "blur" }],
  email: [{ required: true, type: "email", message: "邮箱格式不正确", trigger: "blur" }],
  password: [{ required: true, min: 6, message: "密码至少 6 位", trigger: "blur" }],
}

async function onLogin() {
  if (!(await loginForm.value?.validate().catch(() => false))) return
  loginError.value = ""
  busy.value = true
  try {
    await auth.login(loginData.username, loginData.password)
    router.push("/")
  } catch (e) {
    loginError.value = (e as ApiError).status === 401 ? "用户名或密码错误" : (e as ApiError).message
  } finally {
    busy.value = false
  }
}

async function onRegister() {
  if (!(await regForm.value?.validate().catch(() => false))) return
  regError.value = ""
  busy.value = true
  try {
    await auth.register({
      username: regData.username, email: regData.email,
      password: regData.password, display_name: regData.display_name || null,
    })
    ElMessage.success("注册成功，请登录")
    tab.value = "login"
  } catch (e) {
    const err = e as ApiError
    regError.value = err.status === 403 ? "注册已关闭"
      : err.status === 409 ? "用户名或邮箱已被占用" : err.message
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.login-wrap { display: flex; justify-content: center; padding-top: 80px; }
.login-card { width: 380px; }
</style>
