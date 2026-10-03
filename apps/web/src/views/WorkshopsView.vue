<script setup lang="ts">
import { formatDateTime } from '@/utils/dateTime'
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import WorkshopManagement from '@/components/WorkshopManagement.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api'
import { useSession } from '@/stores/session'
import type { components } from '@future/api-client'
type Workshop = components['schemas']['Workshop']
type Registration = components['schemas']['Registration']
type Member = components['schemas']['Membership']
type School = components['schemas']['Institution']
const session = useSession(),
  workshops = ref<Workshop[]>([]),
  registrations = ref<Registration[]>([]),
  members = ref<Member[]>([]),
  schools = ref<School[]>([]),
  loading = ref(true),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  school = ref(''),
  chosen = ref<number[]>([]),
  groupWorkshop = ref('')
async function load() {
  loading.value = true
  error.value = ''
  try {
    ;[workshops.value, registrations.value] = await Promise.all([
      api<Workshop[]>('workshops/'),
      api<Registration[]>('registrations/'),
    ])
    if (session.staff) {
      ;[schools.value, members.value] = await Promise.all([
        api<School[]>('institutions/'),
        api<Member[]>('memberships/'),
      ])
    }
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
async function register(id: string, group = false) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const r = await api<Registration[]>(
      'workshops/' + id + '/register/',
      'POST',
      group ? { school: school.value, users: chosen.value } : {},
    )
    message.value = r
      .map((x) => (x.status === 'confirmed' ? 'Запись подтверждена' : 'Добавлены в лист ожидания'))
      .join(' · ')
    await load()
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}
async function cancel(id: string) {
  if (busy.value || !window.confirm('Отменить участие?')) return
  busy.value = true
  try {
    await api('registrations/' + id + '/cancel/', 'POST')
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
      <p class="eyebrow">НОВЫЙ ОПЫТ</p>
      <h1>Мастер-классы в вузе</h1>
      <p class="subtitle">Для участия не нужны запись на курс или учебный проект.</p>
    </div>
  </div>
  <p v-if="message" class="success">{{ message }}</p>
  <PageState :loading="loading" :error="error" :empty="!workshops.length" @retry="load"
    ><div class="grid">
      <article v-for="w in workshops" :key="w.id" class="panel">
        <div class="card-icon"><i class="pi pi-sparkles" /></div>
        <span class="tag">{{ w.topic }}</span>
        <h3 style="margin-top: 14px">{{ w.title }}</h3>
        <p class="helper">{{ w.description }}</p>
        <p class="card-meta">
          {{ formatDateTime(w.starts_at) }} ·
          {{ w.format === 'online' ? 'Онлайн' : 'Очно' }}
        </p>
        <p class="helper">
          <a v-if="w.online_url" :href="w.online_url" target="_blank" rel="noopener noreferrer"
            >Ссылка занятия</a
          >
          {{ w.location }} · возраст {{ w.min_age }}–{{ w.max_age }}<br />{{ w.requirements }}
        </p>
        <span class="badge">Свободных мест: {{ w.available }}</span>
        <p class="helper">Регистрация до {{ formatDateTime(w.registration_closes_at) }}</p>
        <div class="actions">
          <Button
            v-if="
              w.status === 'published' &&
              new Date(w.registration_opens_at) <= new Date() &&
              new Date(w.registration_closes_at) >= new Date()
            "
            :label="w.available ? 'Записаться' : 'В лист ожидания'"
            :loading="busy"
            @click="register(w.id)"
          /><Button
            v-if="session.staff && w.status === 'published'"
            label="От школы"
            text
            @click="groupWorkshop = w.id"
          />
        </div>
      </article>
    </div>
    <section v-if="groupWorkshop" class="panel" style="margin-top: 24px">
      <h2>Групповая заявка школы</h2>
      <form class="form" @submit.prevent="register(groupWorkshop, true)">
        <label
          >Школа<select v-model="school" required>
            <option
              v-for="s in schools.filter((x) => x.kind === 'school')"
              :key="s.id"
              :value="s.id"
            >
              {{ s.name }}
            </option>
          </select></label
        ><label
          >Участники<select v-model="chosen" multiple required size="6">
            <option v-for="m in members" :key="m.id" :value="m.user">
              {{ m.name }} · {{ m.email }}
            </option>
          </select></label
        ><Button type="submit" label="Подать заявку" :loading="busy" />
      </form>
    </section>
    <div class="section-heading"><h2>Ваши заявки</h2></div>
    <div class="panel">
      <p v-if="!registrations.length" class="helper">Вы ещё не записаны.</p>
      <div v-for="r in registrations" :key="r.id" class="card-foot">
        <span>{{ workshops.find((w) => w.id === r.workshop)?.title }} · {{ r.status }}</span
        ><Button v-if="r.status !== 'cancelled'" label="Отменить" text @click="cancel(r.id)" />
      </div></div
  ></PageState>
  <WorkshopManagement @changed="load" />
</template>
