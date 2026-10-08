<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import Button from 'primevue/button'
import { api } from '@/api'
import FormFeedback from '../../common/FormFeedback/FormFeedback.vue'
import { useOperation } from '@/composables/useOperation'
import type { components } from '@future/api-client'
const props = defineProps<{ lesson: components['schemas']['Lesson'] }>(),
  op = useOperation(),
  members = ref<components['schemas']['Membership'][]>([]),
  rows = ref<components['schemas']['Attendance'][]>([])
async function load() {
  ;[members.value, rows.value] = await Promise.all([
    api<components['schemas']['Membership'][]>('memberships/?classroom=' + props.lesson.classroom),
    api<components['schemas']['Attendance'][]>('attendance/?lesson=' + props.lesson.id),
  ])
  if (props.lesson.course) {
    const enrollments = await api<components['schemas']['Enrollment'][]>(
      'enrollments/?course=' + props.lesson.course,
    )
    members.value = members.value.filter((m) =>
      enrollments.some((e) => e.user === m.user && e.status !== 'cancelled'),
    )
  }
}
async function mark(user: number, present: boolean) {
  const row = rows.value.find((x) => x.user === user)
  const result = await op.execute(() =>
    row
      ? api('attendance/' + row.id + '/', 'PATCH', { present }, row.updated_at)
      : api('attendance/', 'POST', { lesson: props.lesson.id, user, present }),
  )
  if (result) await load()
}
onMounted(() => void op.execute(load, ''))
watch(
  () => props.lesson.id,
  () => void op.execute(load, ''),
)
</script>
<template>
  <section class="panel">
    <h3>Посещаемость · {{ lesson.title }}</h3>
    <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
    <p v-if="!members.length" class="helper">Нет участников класса.</p>
    <div v-for="m in members" :key="m.id" class="card-foot">
      <span
        >{{ m.name }} ·
        {{
          rows.find((x) => x.user === m.user)?.present
            ? 'присутствовал'
            : rows.some((x) => x.user === m.user)
              ? 'отсутствовал'
              : 'не отмечен'
        }}</span
      >
      <div class="actions">
        <Button
          label="Присутствовал"
          text
          :disabled="op.busy.value"
          @click="mark(m.user, true)"
        /><Button
          label="Отсутствовал"
          text
          :disabled="op.busy.value"
          @click="mark(m.user, false)"
        />
      </div>
    </div>
  </section>
</template>
