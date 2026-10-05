<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/dateTime'
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import PageState from '@/components/PageState.vue'
import { api } from '@/api'
type Option = { id: string; name?: string; title?: string; user?: number }
type Metrics = {
  participants: {
    id: number
    display_name: string
    first_name: string
    last_name: string
    email: string
    email_verified_at: string | null
  }[]
  updated_at: string
  learning: Record<string, number>
  workshops: Record<string, number>
}
const institutions = ref<Option[]>([]),
  classes = ref<Option[]>([]),
  courses = ref<Option[]>([]),
  teachers = ref<Option[]>([]),
  filters = ref({ institution: '', classroom: '', teacher: '', course: '', from: '', to: '' }),
  data = ref<Metrics>(),
  loading = ref(false),
  error = ref('')
const labels: Record<string, string> = {
  login_events: 'Входов за период',
  course_submitted_works: 'Отправки курса',
  course_accepted_works: 'Принятые работы курса',
  course_completed_enrollments: 'Завершённые записи',
  course_overdue_assignments: 'Просроченные задания курса',
  course_assignments: 'Задания курсов',
  registered: 'Зарегистрированы',
  email_verified: 'Подтвердили почту',
  logged_in_during_period: 'Входили за период',
  educationally_active: 'Учебно активны',
  learning_actions: 'Учебные действия',
  invited_unregistered: 'Приглашены без регистрации',
  pending_invitations: 'Ожидающие приглашения',
  enrollments: 'Записи на курсы',
  attendance_present: 'Посещённые занятия',
  projects: 'Проекты',
  tasks: 'Задания',
  accepted_tasks: 'Принятые задания',
  submitted_tasks: 'Отправленные задания',
  overdue_tasks: 'Просроченные задания',
  projects_requiring_attention: 'Проекты требуют внимания',
  progress_percent: 'Принятые задания, %',
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(filters.value)) {
      if (v) params.set(k, k === 'from' || k === 'to' ? new Date(v).toISOString() : v)
    }
    data.value = await api<Metrics>('crm/?' + params)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
onMounted(async () => {
  try {
    ;[institutions.value, classes.value, courses.value, teachers.value] = await Promise.all([
      api<Option[]>('institutions/'),
      api<Option[]>('classrooms/'),
      api<Option[]>('courses/'),
      api<Option[]>('staff/'),
    ])
  } catch (e) {
    error.value = errorMessage(e)
  }
  await load()
})
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">РЕЗУЛЬТАТЫ ОБУЧЕНИЯ</p>
      <h1>CRM образовательной работы</h1>
      <p class="subtitle">Только доступные вам учреждения и классы.</p>
    </div>
  </div>
  <form class="filters" @submit.prevent="load">
    <select v-model="filters.institution" aria-label="Учреждение">
      <option value="">Все учреждения</option>
      <option v-for="o in institutions" :key="o.id" :value="o.id">{{ o.name }}</option></select
    ><select v-model="filters.classroom" aria-label="Класс">
      <option value="">Все классы</option>
      <option v-for="o in classes" :key="o.id" :value="o.id">{{ o.name }}</option></select
    ><select v-model="filters.teacher" aria-label="Преподаватель">
      <option value="">Все преподаватели</option>
      <option v-for="o in teachers" :key="o.id" :value="o.user">
        {{ o.name || o.user }}
      </option></select
    ><select v-model="filters.course" aria-label="Курс">
      <option value="">Все курсы</option>
      <option v-for="o in courses" :key="o.id" :value="o.id">{{ o.title }}</option></select
    ><input v-model="filters.from" type="datetime-local" aria-label="Начало периода" /><input
      v-model="filters.to"
      type="datetime-local"
      aria-label="Конец периода"
    /><Button type="submit" label="Применить" />
  </form>
  <PageState :loading="loading" :error="error" @retry="load"
    ><p class="helper">
      Обновлено {{ data ? formatDateTime(data.updated_at) : '' }}. По умолчанию период — последние
      30 дней.
    </p>
    <div class="grid">
      <div v-for="(value, key) in data?.learning" :key="key" class="panel stat">
        <span class="stat-label">{{ labels[key] || key }}</span>
        <div class="stat-value">{{ value }}</div>
      </div>
    </div>
    <div class="section-heading"><h2>Мастер-классы · отдельно от курсов</h2></div>
    <div class="grid">
      <div v-for="(value, key) in data?.workshops" :key="key" class="panel stat">
        <span class="stat-label">{{
          key === 'confirmed'
            ? 'Подтверждённые записи'
            : key === 'waiting'
              ? 'Лист ожидания'
              : 'Посетили'
        }}</span>
        <div class="stat-value">{{ value }}</div>
      </div>
    </div>
    <p class="helper">
      Учебная активность — отправка задания, загрузка версии документа или изменение проекта за
      период. Вход в систему считается отдельно. Прогресс — доля заданий с хотя бы одним принятым
      результатом; отправленная работа сама по себе не считается принятой. Показатель «сейчас
      онлайн» не реализован.
    </p></PageState
  >
  <section v-if="data" class="panel">
    <h2>Участники выбранной области</h2>
    <p class="helper">До 500 участников. Уточните фильтр учреждения или класса.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ФИО</th>
            <th>Почта</th>
            <th>Подтверждение почты</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in data.participants" :key="p.id">
            <td>{{ p.display_name || [p.first_name, p.last_name].join(' ') }}</td>
            <td>{{ p.email }}</td>
            <td>{{ p.email_verified_at ? 'Подтверждена' : 'Ожидает' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
