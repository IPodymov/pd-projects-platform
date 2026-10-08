<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import { api } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import FormFeedback from '@/components/common/FormFeedback/FormFeedback.vue'
const session = useSession(),
  router = useRouter(),
  op = useOperation()
const form = ref({ display_name: '', email: '', password: '', date_of_birth: '' })
const repeatPassword = ref(''),
  pending = ref(''),
  code = ref('')
function changeDetails() {
  pending.value = ''
  code.value = ''
}
async function requestCode() {
  await op.execute(async () => {
    if (form.value.password !== repeatPassword.value) throw Error('Пароли не совпадают')
    await session.refresh()
    const result = await api<{ id: string; detail: string }>('registration/request/', 'POST', {
      ...form.value,
      date_of_birth: form.value.date_of_birth || null,
    })
    pending.value = result.id
    code.value = ''
  }, 'Код отправлен на вашу почту. Он действует 15 минут.')
}
async function confirm() {
  await op.execute(async () => {
    await api('registration/confirm/', 'POST', { id: pending.value, code: code.value })
    form.value.password = repeatPassword.value = ''
    await session.refresh()
    await router.push('/account')
  }, 'Аккаунт создан')
}
</script>
<template>
  <p v-if="session.user?.id">
    Вы уже вошли. <RouterLink to="/account">Открыть аккаунт</RouterLink>
  </p>
  <template v-else>
    <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
    <form v-if="!pending" class="form" @submit.prevent="requestCode">
      <label
        >ФИО<input v-model="form.display_name" autocomplete="name" required maxlength="200"
      /></label>
      <label>Email<input v-model="form.email" type="email" autocomplete="email" required /></label>
      <label
        >Дата рождения (необязательно)<input
          v-model="form.date_of_birth"
          type="date"
          autocomplete="bday"
      /></label>
      <label
        >Пароль<input
          v-model="form.password"
          type="password"
          autocomplete="new-password"
          required
          minlength="8"
          maxlength="128"
      /></label>
      <label
        >Повторите пароль<input
          v-model="repeatPassword"
          type="password"
          autocomplete="new-password"
          required
          minlength="8"
          maxlength="128"
      /></label>
      <p class="helper">Не менее 8 символов. Используйте пароль, который трудно угадать.</p>
      <Button type="submit" label="Получить код подтверждения" :loading="op.busy.value" />
    </form>
    <form v-else class="form" @submit.prevent="confirm">
      <p>Введите код из письма на {{ form.email }}.</p>
      <label
        >Код подтверждения<input
          v-model="code"
          pattern="[0-9]{6}"
          maxlength="6"
          inputmode="numeric"
          autocomplete="one-time-code"
          required
      /></label>
      <Button type="submit" label="Подтвердить и зарегистрироваться" :loading="op.busy.value" />
      <Button
        label="Отправить код повторно"
        severity="secondary"
        :disabled="op.busy.value"
        @click="requestCode"
      />
      <Button label="Изменить данные" text :disabled="op.busy.value" @click="changeDetails" />
      <p class="helper">
        Повторная отправка доступна через минуту. После пяти неверных попыток нужен новый код.
      </p>
    </form>
    <p class="helper">
      После регистрации администратор добавит вас в класс, курсы и проекты. Если у вас есть
      приглашение, откройте ссылку из письма после входа.
    </p>
  </template>
</template>
<style src="./RegistrationForm.css" scoped></style>
