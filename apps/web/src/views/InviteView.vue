<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
import { ref } from 'vue'
import Button from 'primevue/button'
import { api } from '@/api'
const token = window.location.hash.slice(1)
window.history.replaceState(null, '', window.location.pathname)
const code = ref(''),
  password = ref(''),
  message = ref(''),
  error = ref(''),
  busy = ref(false)
async function run(accept = false) {
  error.value = ''
  busy.value = true
  try {
    const result = await api<{ detail: string }>(
      accept ? 'invitation-accept/' : 'invitation-code/',
      'POST',
      accept ? { token, code: code.value, password: password.value } : { token },
    )
    message.value = result.detail
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="auth panel">
    <p class="eyebrow">ПРИГЛАШЕНИЕ</p>
    <h1>Ваш первый шаг</h1>
    <p>
      Подтвердите доступ к почте, на которую вас пригласили. Ссылка сама по себе не завершает
      регистрацию.
    </p>
    <div v-if="!token" class="state error">
      Откройте полную ссылку из письма. Токен не сохраняется в адресной строке.
    </div>
    <template v-else
      ><Button label="Отправить код на почту" severity="secondary" :loading="busy" @click="run()" />
      <form class="form" data-layout="inviteview-style-1" @submit.prevent="run(true)">
        <label
          >Код из письма<input
            v-model="code"
            inputmode="numeric"
            pattern="[0-9]{6}"
            maxlength="6"
            required
            autocomplete="one-time-code" /></label
        ><label
          >Ваш пароль<input v-model="password" type="password" autocomplete="new-password"
        /></label>
        <p class="helper">
          Для нового аккаунта: минимум 8 символов, не только цифры. Если аккаунт уже существует,
          сначала войдите с этой почтой; пароль здесь менять не нужно.
        </p>
        <Button type="submit" label="Принять приглашение" :loading="busy" /></form
    ></template>
    <p v-if="message" class="success" role="status">{{ message }}</p>
    <p v-if="error" class="state error" role="alert">{{ error }}</p>
    <RouterLink to="/login">Перейти ко входу →</RouterLink>
  </div>
</template>
<style src="./InviteView.css" scoped></style>
