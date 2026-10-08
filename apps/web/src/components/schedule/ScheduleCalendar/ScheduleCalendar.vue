<script setup lang="ts">
import { computed } from 'vue'
import type { components } from '@future/api-client'
type Lesson = components['schemas']['Lesson']
const props = defineProps<{ lessons: Lesson[]; days: Date[]; mode: string }>()
defineEmits<{ select: [lesson: Lesson] }>()
function onDay(lesson: Lesson, day: Date) {
  return new Date(lesson.starts_at).toDateString() === day.toDateString()
}
const visible = computed(() =>
  props.lessons.filter((lesson) => props.days.some((day) => onDay(lesson, day))),
)
const hours = computed(() => {
  const starts = visible.value.map((l) => new Date(l.starts_at).getHours())
  const ends = visible.value.map((l) => new Date(l.ends_at).getHours())
  const first = Math.min(9, ...starts),
    last = Math.max(17, ...ends)
  return Array.from({ length: last - first + 1 }, (_, index) => first + index)
})
function atHour(lesson: Lesson, day: Date, hour: number) {
  return onDay(lesson, day) && new Date(lesson.starts_at).getHours() === hour
}
function time(value: string) {
  return new Date(value).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })
}
</script>
<template>
  <section class="panel calendar-container">
    <p v-if="!visible.length" class="helper calendar-empty">
      На выбранный период занятий пока нет.
    </p>
    <table v-if="mode === 'week'" class="week-calendar">
      <thead>
        <tr>
          <th class="time-label">Время</th>
          <th
            v-for="day in days"
            :key="day.toISOString()"
            :class="{ today: day.toDateString() === new Date().toDateString() }"
          >
            {{ day.toLocaleDateString('ru', { weekday: 'short', day: 'numeric', month: 'short' }) }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="hour in hours" :key="hour">
          <th class="time-label">{{ String(hour).padStart(2, '0') }}:00</th>
          <td v-for="day in days" :key="day.toISOString()">
            <button
              v-for="lesson in visible.filter((l) => atHour(l, day, hour))"
              :key="lesson.id"
              class="calendar-event"
              :class="{
                'course-event': !!lesson.course,
                'cancelled-event': lesson.status === 'cancelled',
              }"
              @click="$emit('select', lesson)"
            >
              <span>{{ time(lesson.starts_at) }}–{{ time(lesson.ends_at) }}</span
              ><strong>{{ lesson.title }}</strong
              ><span>{{ lesson.format === 'online' ? 'Онлайн' : lesson.room || 'Очно' }}</span>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="month-calendar">
      <div v-for="day in days" :key="day.toISOString()" class="calendar-day">
        <strong>{{ day.toLocaleDateString('ru', { day: 'numeric', month: 'short' }) }}</strong
        ><button
          v-for="lesson in visible.filter((l) => onDay(l, day))"
          :key="lesson.id"
          class="calendar-event"
          @click="$emit('select', lesson)"
        >
          <span>{{ time(lesson.starts_at) }}</span
          ><strong>{{ lesson.title }}</strong>
        </button>
      </div>
    </div>
  </section>
</template>
<style src="./ScheduleCalendar.css" scoped></style>
