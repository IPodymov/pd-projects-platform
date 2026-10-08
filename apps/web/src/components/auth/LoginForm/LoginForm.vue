<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
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
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <form class="form" @submit.prevent="submit">
    <label>Email<InputText v-model="email" type="email" autocomplete="username" required /></label
    ><label
      >Пароль<InputText v-model="password" type="password" autocomplete="current-password" required
    /></label>
    <div v-if="error" class="state error" role="alert">{{ error }}</div>
    <Button type="submit" label="Войти" icon="pi pi-arrow-right" icon-pos="right" :loading="busy" />
  </form>
  <p class="helper">Забыли пароль? Обратитесь к администратору вашего учреждения.</p>
</template>
<style src="./LoginForm.css" scoped></style>
