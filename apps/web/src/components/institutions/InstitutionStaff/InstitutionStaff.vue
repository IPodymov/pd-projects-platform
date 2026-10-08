<script setup lang="ts">
import type { components } from '@future/api-client'
defineProps<{
  title: string
  staff: components['schemas']['Staff'][]
  institutions: components['schemas']['Institution'][]
}>()
</script>
<template>
  <section class="panel">
    <div class="staff-heading">
      <h2>{{ title }}</h2>
      <RouterLink to="/manage/invitations">Добавить</RouterLink>
    </div>
    <ul>
      <li v-for="person in staff" :key="person.id">
        <span class="staff-avatar">{{ (person.name || 'У').slice(0, 1) }}</span>
        <div>
          <strong>{{ person.name || 'Пользователь ' + person.user }}</strong>
          <p>{{ institutions.find((i) => i.id === person.institution)?.name }}</p>
        </div>
      </li>
    </ul>
    <p v-if="!staff.length" class="helper">Активных назначений пока нет.</p>
  </section>
</template>
<style src="./InstitutionStaff.css" scoped></style>
