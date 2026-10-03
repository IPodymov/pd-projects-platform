<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import Button from 'primevue/button'
import FormFeedback from './FormFeedback.vue'
import { api } from '@/api'
import { useOperation } from '@/composables/useOperation'
import { useSession } from '@/stores/session'
import type { components } from '@future/api-client'
const props = defineProps<{ project: string }>()
type Repository = components['schemas']['Repository']
type Pull = components['schemas']['Pull']
type Review = components['schemas']['LearningReview']
const session = useSession(),
  op = useOperation(),
  repos = ref<Repository[]>([]),
  pulls = ref<Pull[]>([]),
  reviews = ref<Review[]>([]),
  jobs = ref<components['schemas']['Sync'][]>([]),
  staff = ref<components['schemas']['Staff'][]>([]),
  owner = ref(''),
  name = ref(''),
  provider = ref<'github' | 'gitverse'>('github'),
  reviewer = ref<number>(),
  remarks = ref<Record<string, string>>({})
let timer: ReturnType<typeof setTimeout> | undefined
async function load() {
  clearTimeout(timer)
  repos.value = await api<Repository[]>('repositories/?project=' + props.project)
  const ids = new Set(repos.value.map((x) => x.id))
  const rows = await Promise.all([
    api<Pull[]>('pull-requests/'),
    api<Review[]>('git-reviews/'),
    api<components['schemas']['Sync'][]>('git-sync/'),
  ])
  pulls.value = rows[0].filter((x) => ids.has(x.repository))
  const pullIds = new Set(pulls.value.map((x) => x.id))
  reviews.value = rows[1].filter((x) => pullIds.has(x.pull_request))
  jobs.value = rows[2].filter((x) => ids.has(x.repository))
  if (session.staff) staff.value = await api<components['schemas']['Staff'][]>('staff/')
  if (jobs.value.some((x) => x.status === 'queued' || x.status === 'processing'))
    timer = setTimeout(() => void op.execute(load, ''), 2000)
}
async function run(path: string, data?: unknown) {
  const result = await op.execute(() => api(path, 'POST', data))
  if (result) await load()
}
onMounted(() => void op.execute(load, ''))
onBeforeUnmount(() => clearTimeout(timer))
</script>
<template>
  <section class="panel">
    <h2>Репозитории и учебная проверка PR</h2>
    <p class="helper">Проверка относится к конкретному коммиту. Статус PR сохраняется отдельно.</p>
    <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
    <form
      v-if="session.staff"
      class="form"
      @submit.prevent="run('repositories/', { project, provider, owner, name })"
    >
      <label
        >Провайдер<select v-model="provider">
          <option value="github">GitHub</option>
          <option value="gitverse">GitVerse</option>
        </select></label
      ><label>Владелец<input v-model="owner" required pattern="[A-Za-z0-9_.-]+" /></label
      ><label>Репозиторий<input v-model="name" required pattern="[A-Za-z0-9_.-]+" /></label
      ><Button type="submit" label="Связать" :loading="op.busy.value" />
    </form>
    <p v-if="!repos.length" class="helper">Репозиторий ещё не связан.</p>
    <article v-for="r in repos" :key="r.id">
      <h3>{{ r.provider }} · {{ r.owner }}/{{ r.name }}</h3>
      <p>{{ r.enabled ? 'Соединение утверждено' : 'Ожидает утверждения платформой' }}</p>
      <div class="actions">
        <Button
          v-if="session.user?.platform_admin && !r.enabled"
          label="Утвердить соединение"
          :disabled="op.busy.value"
          @click="run('repositories/' + r.id + '/approve/')"
        /><Button
          v-if="session.staff && r.enabled"
          label="Синхронизировать"
          :loading="op.busy.value"
          @click="run('repositories/' + r.id + '/sync/')"
        />
      </div>
      <p v-for="job in jobs.filter((x) => x.repository === r.id)" :key="job.id" class="helper">
        Синхронизация: {{ job.status }} {{ job.error_code }}
      </p>
      <article v-for="pr in pulls.filter((x) => x.repository === r.id)" :key="pr.id" class="panel">
        <h3>
          <a :href="pr.url" target="_blank" rel="noopener noreferrer"
            >#{{ pr.external_number }} {{ pr.title }}</a
          >
        </h3>
        <p>
          PR: {{ pr.status }} · коммит <code>{{ pr.head_sha.slice(0, 12) }}</code>
        </p>
        <form
          v-if="session.staff"
          class="form"
          @submit.prevent="run('pull-requests/' + pr.id + '/assign/', { reviewer })"
        >
          <label
            >Проверяющий<select v-model="reviewer" required>
              <option v-for="s in staff.filter((x) => x.active)" :key="s.id" :value="s.user">
                {{ s.name }} · {{ s.role }}
              </option>
            </select></label
          ><Button type="submit" label="Назначить" :disabled="op.busy.value" />
        </form>
        <div v-for="review in reviews.filter((x) => x.pull_request === pr.id)" :key="review.id">
          <p>
            Учебная проверка: {{ review.result }} · {{ review.revision.slice(0, 12) }}
            {{ review.stale ? '— появились новые коммиты' : '' }}
          </p>
          <p>{{ review.remarks }}</p>
          <div
            v-if="
              review.result === 'pending' && !review.stale && review.reviewer === session.user?.id
            "
            class="form"
          >
            <label>Замечания<textarea v-model="remarks[review.id]" /></label>
            <div class="actions">
              <Button
                label="Принять"
                :disabled="op.busy.value"
                @click="
                  run('git-reviews/' + review.id + '/decide/', {
                    result: 'accepted',
                    remarks: remarks[review.id] || '',
                  })
                "
              /><Button
                label="Доработка"
                :disabled="op.busy.value"
                @click="
                  run('git-reviews/' + review.id + '/decide/', {
                    result: 'revision',
                    remarks: remarks[review.id] || '',
                  })
                "
              />
            </div>
          </div>
        </div>
      </article>
    </article>
  </section>
</template>
