<script setup lang="ts">
import { inject } from 'vue'
import { usersManagementKey } from '@/composables/useUsersManagement'
import Button from 'primevue/button'
import PageState from '@/components/common/PageState/PageState.vue'
const { op, rows, loading, error, search, page, count, classroomName, choose, load, find, changePage } = inject(usersManagementKey)!
</script>
<template>
  <form class="filters" @submit.prevent="find">
    <input
      v-model="search"
      aria-label="Поиск по имени или почте"
      placeholder="Имя или email"
    /><Button type="submit" label="Найти" />
  </form>
  <PageState :loading="loading" :error="error" @retry="load">
    <p v-if="!rows.length">Пользователи не найдены.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Пользователь</th>
            <th>Классы</th>
            <th>Статус</th>
            <th>Действие</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in rows" :key="user.id">
            <td>{{ user.name || 'Без имени' }}<br />{{ user.email }}</td>
            <td>
              <p v-for="m in user.memberships.filter((m) => !m.ended_at)" :key="m.id">
                {{ classroomName(m.classroom) }}
              </p>
            </td>
            <td>
              {{ user.is_active ? 'Активен' : 'Отключён' }} ·
              {{ user.email_verified_at ? 'Почта подтверждена' : 'Почта не подтверждена' }}
            </td>
            <td>
              <Button label="Редактировать" text :disabled="op.busy.value" @click="choose(user)" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="actions">
      <Button label="Назад" :disabled="page === 1" @click="changePage(-1)" /><span
        >Страница {{ page }} · всего {{ count }}</span
      ><Button label="Далее" :disabled="page * 50 >= count" @click="changePage(1)" />
    </div>
  </PageState>
</template>
<style src="./UserDirectory.css" scoped></style>
