<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import { api } from '@/api'
import { useSession } from '@/stores/session'
const session = useSession(),
  email = ref(''),
  password = ref(''),
  code = ref(''),
  id = ref(''),
  message = ref(''),
  error = ref(''),
  busy = ref(false)
const profile = ref({ display_name: '', date_of_birth: '' }),
  profilePassword = ref('')
onMounted(async () => {
  try {
    const result = await api<{ display_name: string; date_of_birth: string | null }>('profile/')
    profile.value = { display_name: result.display_name, date_of_birth: result.date_of_birth || '' }
  } catch (e) {
    error.value = errorMessage(e)
  }
})
async function saveProfile() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await api('profile/', 'POST', {
      display_name: profile.value.display_name,
      date_of_birth: profile.value.date_of_birth || null,
      password: profilePassword.value,
    })
    await session.refresh()
    message.value = 'Профиль обновлён'
    profilePassword.value = ''
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function submit() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    if (id.value) {
      await api('email-change/confirm/', 'POST', { id: id.value, code: code.value })
      await session.refresh()
      message.value = 'Почта подтверждена и изменена'
      id.value = ''
      password.value = ''
    } else {
      const r = await api<{ id: string; detail: string }>('email-change/request/', 'POST', {
        email: email.value,
        password: password.value,
      })
      id.value = r.id
      message.value = r.detail
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">ЛИЧНЫЕ ДАННЫЕ</p>
      <h1>Ваш аккаунт</h1>
      <p class="subtitle">{{ session.user?.email }}</p>
    </div>
  </div>
  <div class="panel">
    <h2>Профиль</h2>
    <form class="form" @submit.prevent="saveProfile">
      <label>ФИО<input v-model="profile.display_name" maxlength="200" required /></label
      ><label>Дата рождения<input v-model="profile.date_of_birth" type="date" /></label>
      <p class="helper">Дата рождения нужна для мастер-классов с возрастными ограничениями.</p>
      <label
        >Текущий пароль<input
          v-model="profilePassword"
          type="password"
          autocomplete="current-password"
          required /></label
      ><Button type="submit" label="Сохранить профиль" :loading="busy" />
    </form>
    <h2>Изменить почту</h2>
    <form class="form" @submit.prevent="submit">
      <template v-if="!id"
        ><label>Новый email<input v-model="email" type="email" required /></label
        ><label
          >Текущий пароль<input
            v-model="password"
            type="password"
            autocomplete="current-password"
            required /></label></template
      ><label v-else
        >Код с новой почты<input
          v-model="code"
          pattern="[0-9]{6}"
          inputmode="numeric"
          autocomplete="one-time-code"
          required /></label
      ><Button
        type="submit"
        :label="id ? 'Подтвердить новую почту' : 'Отправить код'"
        :loading="busy"
      />
    </form>
    <p v-if="message" class="success" role="status">{{ message }}</p>
    <p v-if="error" class="state error" role="alert">{{ error }}</p>
  </div>
</template>
