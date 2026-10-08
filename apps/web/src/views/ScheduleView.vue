<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
import { ref, onMounted, computed } from 'vue'
import Button from 'primevue/button'
import ScheduleLessonForm from '@/components/schedule/ScheduleLessonForm/ScheduleLessonForm.vue'
import ScheduleCalendar from '@/components/schedule/ScheduleCalendar/ScheduleCalendar.vue'
import LessonAttendance from '@/components/schedule/LessonAttendance/LessonAttendance.vue'
import PageState from '@/components/common/PageState/PageState.vue'
import { api } from '@/api'
import { toLocalDateTime, formatDateTime } from '@/utils/dateTime'
import { useSession } from '@/stores/session'
import type { components } from '@future/api-client'
type Lesson = components['schemas']['Lesson']
type Class = components['schemas']['Classroom']
type Staff = components['schemas']['Staff']
const session = useSession(),
  lessons = ref<Lesson[]>([]),
  classes = ref<Class[]>([]),
  courses = ref<components['schemas']['Course'][]>([]),
  staff = ref<Staff[]>([]),
  mode = ref('week'),
  anchor = ref(new Date().toISOString().slice(0, 10)),
  loading = ref(true),
  error = ref(''),
  busy = ref(false),
  edit = ref<Lesson | null>(null),
  show = ref(false)
const form = ref({
  title: '',
  description: '',
  classroom: '',
  course: null as string | null,
  teacher: 0,
  curator: null as number | null,
  starts_at: '',
  ends_at: '',
  timezone: 'Europe/Moscow',
  format: 'online',
  status: 'scheduled',
  online_url: '',
  location: '',
  room: '',
  repeat_weeks: 1,
})
const days = computed(() => {
  const d = new Date(anchor.value + 'T12:00:00')
  let length = 7
  if (mode.value === 'month') {
    d.setDate(1)
    const offset = (d.getDay() + 6) % 7
    length = Math.ceil((new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate() + offset) / 7) * 7
    d.setDate(d.getDate() - offset)
  } else d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return Array.from({ length }, (_, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n))
})
function navigate(delta: number) {
  const date = new Date(anchor.value + 'T12:00:00')
  if (mode.value === 'month') date.setMonth(date.getMonth() + delta)
  else date.setDate(date.getDate() + delta * 7)
  anchor.value = toLocalDateTime(date.toISOString()).slice(0, 10)
}
function today() {
  anchor.value = toLocalDateTime(new Date().toISOString()).slice(0, 10)
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    lessons.value = await api<Lesson[]>('lessons/')
    if (session.staff) {
      ;[classes.value, staff.value, courses.value] = await Promise.all([
        api<Class[]>('classrooms/'),
        api<Staff[]>('staff/'),
        api<components['schemas']['Course'][]>('courses/'),
      ])
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
function open(l?: Lesson) {
  edit.value = l || null
  show.value = true
  if (l) {
    form.value = {
      ...form.value,
      course: l.course || null,
      ...l,
      starts_at: toLocalDateTime(l.starts_at),
      ends_at: toLocalDateTime(l.ends_at),
    }
  }
}
async function save(series = false) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const d = {
      ...form.value,
      starts_at: new Date(form.value.starts_at).toISOString(),
      ends_at: new Date(form.value.ends_at).toISOString(),
    }
    if (edit.value) {
      const changes = {
        title: d.title,
        description: d.description,
        starts_at: d.starts_at,
        ends_at: d.ends_at,
        timezone: d.timezone,
        format: d.format,
        status: d.status,
        online_url: d.online_url,
        location: d.location,
        room: d.room,
      }
      if (series) {
        await api(
          'lessons/' + edit.value.id + '/change_series/',
          'POST',
          changes,
          edit.value.updated_at,
        )
      } else
        await api('lessons/' + edit.value.id + '/change/', 'POST', changes, edit.value.updated_at)
    } else await api('lessons/', 'POST', d)
    show.value = false
    await load()
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
      <p class="eyebrow">ВАШЕ ВРЕМЯ</p>
      <h1>Расписание</h1>
      <p class="subtitle">
        Занятия доступных классов. Время отображается в часовом поясе браузера.
      </p>
    </div>
    <Button
      v-if="session.managesSchedule"
      label="Добавить занятие"
      icon="pi pi-plus"
      @click="open()"
    />
  </div>
  <div class="filters calendar-controls">
    <Button
      label="Предыдущая"
      icon="pi pi-chevron-left"
      severity="secondary"
      @click="navigate(-1)"
    />
    <Button label="Сегодня" severity="secondary" @click="today" />
    <Button
      label="Следующая"
      icon="pi pi-chevron-right"
      severity="secondary"
      @click="navigate(1)"
    />
    <input v-model="anchor" type="date" aria-label="Дата календаря" /><select
      v-model="mode"
      aria-label="Представление"
    >
      <option value="month">Месяц</option>
      <option value="week">Неделя</option>
      <option value="list">Список</option>
    </select>
  </div>
  <PageState :loading="loading" :error="error" @retry="load"
    ><ScheduleCalendar
      v-if="mode !== 'list'"
      :lessons="lessons"
      :days="days"
      :mode="mode"
      @select="open"
    />
    <div v-else class="panel table-wrap">
      <table>
        <thead>
          <tr>
            <th>Занятие</th>
            <th>Начало</th>
            <th>Формат</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in lessons" :key="l.id" @click="open(l)">
            <td>
              <button class="calendar-event">{{ l.title }}</button>
            </td>
            <td>{{ formatDateTime(l.starts_at) }}</td>
            <td>{{ l.format === 'online' ? 'Онлайн' : 'Очно' }}</td>
            <td>{{ l.status }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!lessons.length" class="helper">Занятий пока нет.</p>
    </div></PageState
  >
  <section v-if="show" class="panel" data-layout="scheduleview-style-1">
    <h2>{{ edit ? 'Детали занятия' : 'Новое занятие' }}</h2>
    <div v-if="!session.managesSchedule">
      <p>{{ edit?.title }}</p>
      <p>{{ edit?.description }}</p>
      <a v-if="edit?.online_url" :href="edit.online_url" target="_blank" rel="noopener noreferrer"
        >Присоединиться ↗</a
      >
      <p v-else>{{ edit?.location }} · {{ edit?.room }}</p>
    </div>
    <ScheduleLessonForm
      v-else
      v-model="form"
      :edit="edit"
      :classes="classes"
      :courses="courses"
      :staff="staff"
      :busy="busy"
      @save="save"
    />
  </section>
  <LessonAttendance
    v-if="edit && session.staff && new Date(edit.starts_at) <= new Date()"
    :lesson="edit"
  />
</template>
<style src="./ScheduleView.css" scoped></style>
