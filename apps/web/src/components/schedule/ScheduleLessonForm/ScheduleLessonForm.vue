<script setup lang="ts">
import Button from 'primevue/button'
import type { components } from '@future/api-client'
export type LessonForm = {
  title: string
  description: string
  classroom: string
  course: string | null
  teacher: number
  curator: number | null
  starts_at: string
  ends_at: string
  timezone: string
  format: string
  status: string
  online_url: string
  location: string
  room: string
  repeat_weeks: number
}
const form = defineModel<LessonForm>({ required: true })
defineProps<{
  edit: components['schemas']['Lesson'] | null
  classes: components['schemas']['Classroom'][]
  courses: components['schemas']['Course'][]
  staff: components['schemas']['Staff'][]
  busy: boolean
}>()
defineEmits<{ save: [series: boolean] }>()
</script>
<template>
  <form class="form" @submit.prevent="$emit('save', false)">
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
        @click="$emit('save', true)"
      />
    </div>
    <p class="helper">
      Исключения не изменяются вместе с серией. Время всей серии меняется через отмену и создание
      новой.
    </p>
  </form>
</template>
<style src="./ScheduleLessonForm.css" scoped></style>
