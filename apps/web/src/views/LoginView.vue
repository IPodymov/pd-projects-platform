<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import { useSession } from '@/stores/session'
const email = ref(''),
  password = ref(''),
  error = ref(''),
  busy = ref(false),
  session = useSession(),
  router = useRouter()
async function submit() {
  busy.value = true
  error.value = ''
  try {
    await session.refresh()
    await session.login(email.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="auth panel">
    <p class="eyebrow">ДОБРО ПОЖАЛОВАТЬ</p>
    <h1>Продолжим работу?</h1>
    <p class="subtitle">Войдите в свой образовательный кабинет.</p>
    <form class="form" style="margin-top: 28px" @submit.prevent="submit">
      <label>Email<InputText v-model="email" type="email" autocomplete="username" required /></label
      ><label
        >Пароль<InputText
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
      /></label>
      <div v-if="error" class="state error" role="alert">{{ error }}</div>
      <Button
        type="submit"
        label="Войти в кабинет"
        icon="pi pi-arrow-right"
        icon-pos="right"
        :loading="busy"
      />
    </form>
    <p class="helper">
      Регистрация доступна по приглашению учреждения. Преподаватель отправит ссылку на вашу почту.
    </p>
  </div>
</template>
