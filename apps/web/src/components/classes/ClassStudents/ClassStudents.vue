<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api } from '@/api'
import PageState from '@/components/common/PageState/PageState.vue'
import StatusBadge from '@/components/common/StatusBadge/StatusBadge.vue'
import { errorMessage } from '@/utils/errors'
import type { components } from '@future/api-client'
const props = defineProps<{ classroom: string }>()
const members = ref<components['schemas']['Membership'][]>([]),
  projects = ref<components['schemas']['Project'][]>([]),
  loading = ref(true),
  error = ref(''),
  search = ref('')
const active = computed(() => members.value.filter((m) => !m.ended_at))
const visible = computed(() =>
  active.value.filter((m) =>
    (m.name + ' ' + m.email).toLowerCase().includes(search.value.toLowerCase()),
  ),
)
const accepted = computed(() => projects.value.filter((p) => p.status === 'accepted').length)
async function load() {
  loading.value = true
  error.value = ''
  try {
    const results = await Promise.all([
      api<components['schemas']['Membership'][]>('memberships/?classroom=' + props.classroom),
      api<components['schemas']['Project'][]>('projects/'),
    ])
    members.value = results[0]
    projects.value = results[1].filter((p) => p.classroom === props.classroom)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
<template>
  <PageState :loading="loading" :error="error" @retry="load">
    <div class="class-stats">
      <div>
        <span>Учащихся</span><strong>{{ active.length }}</strong>
      </div>
      <div>
        <span>Проектов</span><strong>{{ projects.length }}</strong>
      </div>
      <div>
        <span>На проверке</span
        ><strong>{{ projects.filter((p) => p.status === 'submitted').length }}</strong>
      </div>
      <div>
        <span>Принято</span><strong>{{ accepted }}</strong>
      </div>
    </div>
    <section class="panel">
      <div class="students-heading">
        <h2>Учащиеся и проекты</h2>
        <input
          v-model="search"
          type="search"
          placeholder="Найти ученика"
          aria-label="Поиск учащихся"
        />
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Учащийся</th>
              <th>Проект</th>
              <th>Статус</th>
              <th>Прогресс</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="member in visible" :key="member.id"
              ><tr
                v-for="project in projects.filter((p) => p.members.includes(member.user))"
                :key="project.id"
              >
                <td>{{ member.name || member.email }}</td>
                <td>
                  <RouterLink :to="'/projects/' + project.id">{{ project.title }}</RouterLink>
                </td>
                <td><StatusBadge :status="project.status" /></td>
                <td>{{ project.progress }}%</td>
              </tr>
              <tr v-if="!projects.some((p) => p.members.includes(member.user))">
                <td>{{ member.name || member.email }}</td>
                <td colspan="3" class="helper">Проект ещё не назначен</td>
              </tr></template
            >
          </tbody>
        </table>
      </div>
      <p v-if="!visible.length" class="helper">Учащиеся не найдены.</p>
    </section>
  </PageState>
</template>
<style src="./ClassStudents.css" scoped></style>
