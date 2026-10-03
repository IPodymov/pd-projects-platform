<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Button from 'primevue/button'
import LessonAttendance from '@/components/LessonAttendance.vue'
import PageState from '@/components/PageState.vue'
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
  mode = ref('month'),
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
function onDay(l: Lesson, d: Date) {
  return new Date(l.starts_at).toLocaleDateString() === d.toLocaleDateString()
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
    error.value = String(e)
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
    error.value = String(e)
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
  <div class="filters">
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
    ><div v-if="mode !== 'list'" class="panel calendar-container">
      <p v-if="!lessons.length" class="helper">Занятий пока нет.</p>
      <div class="calendar">
        <div v-for="day in days" :key="day.toISOString()" class="calendar-day">
          <strong>{{
            day.toLocaleDateString('ru', { day: 'numeric', month: 'short', weekday: 'short' })
          }}</strong
          ><button
            v-for="l in lessons.filter((x) => onDay(x, day))"
            :key="l.id"
            class="calendar-event"
            @click="open(l)"
          >
            {{
              new Date(l.starts_at).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })
            }}
            · {{ l.title }}<br />{{ l.status }}
          </button>
        </div>
      </div>
    </div>
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
  <section v-if="show" class="panel" style="margin-top: 24px">
    <h2>{{ edit ? 'Детали занятия' : 'Новое занятие' }}</h2>
    <div v-if="!session.managesSchedule">
      <p>{{ edit?.title }}</p>
      <p>{{ edit?.description }}</p>
      <a v-if="edit?.online_url" :href="edit.online_url" target="_blank" rel="noopener noreferrer"
        >Присоединиться ↗</a
      >
      <p v-else>{{ edit?.location }} · {{ edit?.room }}</p>
    </div>
    <form v-else class="form" @submit.prevent="save()">
      <label>Название<input v-model="form.title" required /></label
      ><template v-if="!edit"
        ><label
          >Класс<select v-model="form.classroom" required>
            <option v-for="cl in classes" :key="cl.id" :value="cl.id">{{ cl.name }}</option>
          </select></label
        ><label
          >Курс (необязательно)<select v-model="form.course">
            <option :value="null">Занятие класса</option>
            <option
              v-for="c in courses.filter(
                (c) =>
                  c.status === 'published' &&
                  c.institution === classes.find((x) => x.id === form.classroom)?.institution,
              )"
              :key="c.id"
              :value="c.id"
            >
              {{ c.title }}
            </option>
          </select></label
        ><label
          >Преподаватель<select v-model="form.teacher" required>
            <option
              v-for="s in staff.filter((s) => s.role === 'teacher')"
              :key="s.id"
              :value="s.user"
            >
              {{ s.name || s.user }}
            </option>
          </select></label
        ></template
      ><label>Начало<input v-model="form.starts_at" type="datetime-local" required /></label
      ><label>Окончание<input v-model="form.ends_at" type="datetime-local" required /></label
      ><label>Часовой пояс серии<input v-model="form.timezone" required /></label
      ><label
        >Формат<select v-model="form.format">
          <option value="online">Онлайн</option>
          <option value="onsite">Очно</option>
        </select></label
      ><label v-if="form.format === 'online'"
        >Ссылка HTTPS<input v-model="form.online_url" type="url" required /></label
      ><template v-else
        ><label>Место<input v-model="form.location" required /></label
        ><label>Аудитория<input v-model="form.room" required /></label></template
      ><label
        >Статус<select v-model="form.status">
          <option value="scheduled">Запланировано</option>
          <option value="rescheduled">Перенесено</option>
          <option value="cancelled">Отменено</option>
          <option value="completed">Проведено</option>
        </select></label
      ><label v-if="!edit"
        >Повторять каждую неделю, всего занятий<input
          v-model.number="form.repeat_weeks"
          type="number"
          min="1"
          max="52"
      /></label>
      <div class="actions">
        <Button
          type="submit"
          :label="edit ? 'Изменить это занятие' : 'Создать занятия'"
          :loading="busy"
        /><Button
          v-if="edit?.series"
          label="Формат и статус всей серии"
          severity="secondary"
          :loading="busy"
          @click="save(true)"
        />
      </div>
      <p class="helper">
        Исключения не изменяются вместе с серией. Время всей серии меняется через отмену и создание
        новой.
      </p>
    </form>
  </section>
  <LessonAttendance
    v-if="edit && session.staff && new Date(edit.starts_at) <= new Date()"
    :lesson="edit"
  />
</template>
