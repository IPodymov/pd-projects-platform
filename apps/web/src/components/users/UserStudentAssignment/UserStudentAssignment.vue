<script setup lang="ts">
import { inject } from 'vue'
import { usersManagementKey } from '@/composables/useUsersManagement'
import Button from 'primevue/button'
const { op, classes, attach, addStudent } = inject(usersManagementKey)!
</script>
<template>
  <section class="panel">
    <h2>Добавить зарегистрированного ученика</h2>
    <p class="helper">
      Введите подтверждённую почту нового пользователя и выберите класс вашего учреждения.
    </p>
    <form class="form" @submit.prevent="addStudent">
      <label>Email<input v-model="attach.email" type="email" required /></label>
      <label
        >Класс<select v-model="attach.classroom" required>
          <option value="">Выберите…</option>
          <option v-for="c in classes" :key="c.id" :value="c.id">
            {{ c.institution_name }} · {{ c.name }} · {{ c.academic_year }}
          </option>
        </select></label
      >
      <Button type="submit" label="Добавить в класс" :loading="op.busy.value" />
    </form>
  </section>
</template>
<style src="./UserStudentAssignment.css" scoped></style>
