<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import Button from 'primevue/button'
import { api } from '@/api'
import FormFeedback from './FormFeedback.vue'
import { useOperation } from '@/composables/useOperation'
import { useSession } from '@/stores/session'
import type { components } from '@future/api-client'
const props = defineProps<{ classroom: string }>(),
  session = useSession(),
  op = useOperation(),
  staff = ref<components['schemas']['Staff'][]>([]),
  assignments = ref<components['schemas']['Teaching'][]>([]),
  members = ref<components['schemas']['Membership'][]>([]),
  classes = ref<components['schemas']['Classroom'][]>([]),
  chosen = ref(''),
  targets = ref<Record<string, string>>({})
async function load() {
  ;[staff.value, assignments.value, members.value, classes.value] = await Promise.all([
    api<components['schemas']['Staff'][]>('staff/'),
    api<components['schemas']['Teaching'][]>('teaching-assignments/'),
    api<components['schemas']['Membership'][]>('memberships/?classroom=' + props.classroom),
    api<components['schemas']['Classroom'][]>('classrooms/'),
  ])
}
async function run(path: string, body: unknown) {
  const result = await op.execute(() => api(path, 'POST', body))
  if (result) await load()
}
async function transfer(m: components['schemas']['Membership']) {
  if (
    !window.confirm(
      'Завершить текущее членство и перевести учащегося? Результаты сохранятся в прежнем классе.',
    )
  )
    return
  await run('memberships/' + m.id + '/transfer/', { classroom: targets.value[m.id] })
}
onMounted(() => void op.execute(load, ''))
watch(
  () => props.classroom,
  () => void op.execute(load, ''),
)
</script>
<template>
  <section class="panel" style="margin-top: 24px">
    <h2>Сотрудники и состав класса</h2>
    <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
    <form
      v-if="session.institutionAdmin"
      class="form"
      @submit.prevent="run('teaching-assignments/', { classroom, staff: chosen })"
    >
      <label
        >Назначить преподавателя<select v-model="chosen" required>
          <option
            v-for="s in staff.filter(
              (s) =>
                s.active &&
                s.role === 'teacher' &&
                s.institution === classes.find((c) => c.id === classroom)?.institution,
            )"
            :key="s.id"
            :value="s.id"
          >
            {{ s.name }}
          </option>
        </select></label
      ><Button type="submit" label="Добавить назначение" :loading="op.busy.value" />
    </form>
    <ul>
      <li v-for="a in assignments.filter((a) => a.classroom === classroom)" :key="a.id">
        {{ staff.find((s) => s.id === a.staff)?.name }} ·
        {{ a.active ? 'назначен' : 'назначение завершено' }}
        <Button
          v-if="session.institutionAdmin"
          :label="a.active ? 'Завершить' : 'Восстановить'"
          text
          :disabled="op.busy.value"
          @click="run('teaching-assignments/' + a.id + '/set_active/', { active: !a.active })"
        />
      </li>
    </ul>
    <p v-if="!members.length" class="helper">Зарегистрированных учащихся пока нет.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ФИО</th>
            <th>Почта</th>
            <th>Членство</th>
            <th v-if="session.institutionAdmin">Перевод</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in members" :key="m.id">
            <td>{{ m.name }}</td>
            <td>{{ m.email }}</td>
            <td>{{ m.started_at }} — {{ m.ended_at || 'сейчас' }}</td>
            <td v-if="session.institutionAdmin">
              <div v-if="!m.ended_at" class="actions">
                <select v-model="targets[m.id]" aria-label="Целевой класс">
                  <option
                    v-for="c in classes.filter(
                      (c) =>
                        c.id !== classroom &&
                        c.institution === classes.find((x) => x.id === classroom)?.institution,
                    )"
                    :key="c.id"
                    :value="c.id"
                  >
                    {{ c.name }} · {{ c.academic_year }}
                  </option></select
                ><Button
                  label="Перевести"
                  :disabled="!targets[m.id] || op.busy.value"
                  @click="transfer(m)"
                />
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <section v-if="session.institutionAdmin">
      <h3>Назначения учреждения</h3>
      <div
        v-for="s in staff.filter(
          (s) => s.institution === classes.find((c) => c.id === classroom)?.institution,
        )"
        :key="s.id"
        class="actions"
      >
        <span>{{ s.name }} · {{ s.role }} · {{ s.active ? 'активно' : 'завершено' }}</span
        ><Button
          v-if="s.role !== 'admin' || session.user?.platform_admin"
          :label="s.active ? 'Завершить назначение' : 'Восстановить назначение'"
          text
          :disabled="op.busy.value"
          @click="run('staff/' + s.id + '/set_active/', { active: !s.active })"
        />
      </div>
    </section>
  </section>
</template>
