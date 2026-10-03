<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Button from 'primevue/button'
import { api } from '@/api'
import { toLocalDateTime } from '@/utils/dateTime'
import FormFeedback from './FormFeedback.vue'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import type { components } from '@future/api-client'
const emit = defineEmits<{ changed: [] }>(),
  session = useSession(),
  op = useOperation(),
  institutions = ref<components['schemas']['Institution'][]>([]),
  workshops = ref<components['schemas']['Workshop'][]>([]),
  partnerships = ref<components['schemas']['Partnership'][]>([]),
  subscriptions = ref<components['schemas']['Subscription'][]>([]),
  groups = ref<components['schemas']['Group'][]>([]),
  registrations = ref<components['schemas']['Registration'][]>([]),
  staff = ref<components['schemas']['Staff'][]>([]),
  editId = ref(''),
  dirty = ref(false),
  subscribeSchool = ref(''),
  partner = ref({ university: '', school: '', starts_on: '', ends_on: '' })
const empty = () => ({
  university: '',
  title: '',
  description: '',
  topic: '',
  min_age: 0,
  max_age: 99,
  requirements: '',
  starts_at: '',
  ends_at: '',
  format: 'onsite',
  location: '',
  online_url: '',
  capacity: 20,
  registration_opens_at: '',
  registration_closes_at: '',
  audience: 'all',
  schools: [] as string[],
  leader: '',
})
const form = ref(empty()),
  organizer = computed(
    () =>
      session.user?.platform_admin ||
      session.user?.roles.includes('organizer') ||
      session.user?.roles.includes('admin'),
  )
useUnsavedChanges(dirty)
async function load() {
  ;[
    institutions.value,
    workshops.value,
    partnerships.value,
    subscriptions.value,
    groups.value,
    registrations.value,
    staff.value,
  ] = await Promise.all([
    api<components['schemas']['Institution'][]>('institutions/'),
    api<components['schemas']['Workshop'][]>('workshops/'),
    api<components['schemas']['Partnership'][]>('partnerships/'),
    api<components['schemas']['Subscription'][]>('subscriptions/'),
    api<components['schemas']['Group'][]>('workshop-groups/'),
    api<components['schemas']['Registration'][]>('registrations/'),
    api<components['schemas']['Staff'][]>('staff/'),
  ])
}
async function run(path: string, body?: unknown, method = 'POST') {
  const result = await op.execute(() => api(path, method, body))
  if (result) {
    await load()
    emit('changed')
  }
  return result
}
function edit(w: components['schemas']['Workshop']) {
  editId.value = w.id
  form.value = {
    university: w.university,
    title: w.title,
    description: w.description,
    topic: w.topic,
    min_age: w.min_age ?? 0,
    max_age: w.max_age ?? 99,
    requirements: w.requirements || '',
    starts_at: toLocalDateTime(w.starts_at),
    ends_at: toLocalDateTime(w.ends_at),
    format: w.format,
    location: w.location,
    online_url: w.online_url || '',
    capacity: w.capacity,
    registration_opens_at: toLocalDateTime(w.registration_opens_at),
    registration_closes_at: toLocalDateTime(w.registration_closes_at),
    audience: w.audience,
    schools: w.schools || [],
    leader: String(w.leader || ''),
  }
  dirty.value = false
}
async function save() {
  const body = {
    ...form.value,
    leader: form.value.leader ? Number(form.value.leader) : null,
    starts_at: new Date(form.value.starts_at).toISOString(),
    ends_at: new Date(form.value.ends_at).toISOString(),
    registration_opens_at: new Date(form.value.registration_opens_at).toISOString(),
    registration_closes_at: new Date(form.value.registration_closes_at).toISOString(),
  }
  if (editId.value) delete (body as Partial<typeof body>).university
  const result = await run(
    'workshops/' + (editId.value ? editId.value + '/' : ''),
    body,
    editId.value ? 'PATCH' : 'POST',
  )
  if (result) {
    dirty.value = false
    editId.value = ''
    form.value = empty()
  }
}
async function cancel(path: string, body?: unknown) {
  if (window.confirm('Подтвердить отмену?')) await run(path, body)
}
onMounted(() => void op.execute(load, ''))
</script>
<template>
  <section v-if="session.staff" class="panel" style="margin-top: 24px">
    <h2>Организация мастер-классов</h2>
    <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
    <form v-if="organizer" class="form" @input="dirty = true" @submit.prevent="save">
      <h3>{{ editId ? 'Изменить мероприятие' : 'Новый мастер-класс' }}</h3>
      <label
        >Вуз<select v-model="form.university" required :disabled="!!editId">
          <option
            v-for="i in institutions.filter((i) => i.kind === 'university')"
            :key="i.id"
            :value="i.id"
          >
            {{ i.name }}
          </option>
        </select></label
      ><label>Название<input v-model="form.title" required /></label
      ><label>Тематика<input v-model="form.topic" required /></label
      ><label>Описание<textarea v-model="form.description" required /></label
      ><label>Требования<textarea v-model="form.requirements" /></label>
      <div class="grid">
        <label
          >Возраст от<input
            v-model.number="form.min_age"
            type="number"
            min="0"
            max="120"
            required /></label
        ><label
          >Возраст до<input
            v-model.number="form.max_age"
            type="number"
            min="0"
            max="120"
            required /></label
        ><label>Мест<input v-model.number="form.capacity" type="number" min="1" required /></label>
      </div>
      <label
        >Ведущий<select v-model="form.leader">
          <option value="">Организатор</option>
          <option
            v-for="s in staff.filter((s) => s.active && s.institution === form.university)"
            :key="s.id"
            :value="s.user"
          >
            {{ s.name }}
          </option>
        </select></label
      >
      <div class="grid">
        <label>Начало<input v-model="form.starts_at" type="datetime-local" required /></label
        ><label>Окончание<input v-model="form.ends_at" type="datetime-local" required /></label
        ><label
          >Открытие записи<input
            v-model="form.registration_opens_at"
            type="datetime-local"
            required /></label
        ><label
          >Закрытие записи<input
            v-model="form.registration_closes_at"
            type="datetime-local"
            required
        /></label>
      </div>
      <label
        >Формат<select v-model="form.format">
          <option value="online">Онлайн</option>
          <option value="onsite">Очно</option>
        </select></label
      ><label v-if="form.format === 'online'"
        >HTTPS ссылка<input v-model="form.online_url" type="url" required /></label
      ><label v-else>Место и аудитория<input v-model="form.location" required /></label
      ><label
        >Аудитория<select v-model="form.audience">
          <option value="all">Все пользователи</option>
          <option value="partners">Школы-партнёры</option>
          <option value="selected">Выбранные партнёры</option>
        </select></label
      ><label v-if="form.audience === 'selected'"
        >Школы<select v-model="form.schools" multiple>
          <option
            v-for="i in institutions.filter((i) => i.kind === 'school')"
            :key="i.id"
            :value="i.id"
          >
            {{ i.name }}
          </option>
        </select></label
      ><Button type="submit" label="Сохранить" :loading="op.busy.value" />
    </form>
    <article
      v-for="w in workshops.filter(
        (w) => w.organizer === session.user?.id || session.user?.platform_admin,
      )"
      :key="w.id"
    >
      <h3>{{ w.title }} · {{ w.status }}</h3>
      <div class="actions">
        <Button
          v-if="['draft', 'published'].includes(w.status)"
          label="Редактировать"
          text
          @click="edit(w)"
        /><Button
          v-if="w.status === 'draft'"
          label="Опубликовать"
          :disabled="op.busy.value"
          @click="run('workshops/' + w.id + '/publish/')"
        /><Button
          v-if="['draft', 'published'].includes(w.status)"
          label="Отменить мероприятие"
          text
          @click="cancel('workshops/' + w.id + '/transition/', { status: 'cancelled' })"
        />
      </div>
    </article>
    <section v-if="session.user?.platform_admin">
      <h3>Партнёрства</h3>
      <form class="form" @submit.prevent="run('partnerships/', partner)">
        <label
          >Вуз<select v-model="partner.university" required>
            <option
              v-for="i in institutions.filter((i) => i.kind === 'university')"
              :key="i.id"
              :value="i.id"
            >
              {{ i.name }}
            </option>
          </select></label
        ><label
          >Школа<select v-model="partner.school" required>
            <option
              v-for="i in institutions.filter((i) => i.kind === 'school')"
              :key="i.id"
              :value="i.id"
            >
              {{ i.name }}
            </option>
          </select></label
        ><label>С<input v-model="partner.starts_on" type="date" required /></label
        ><label>До<input v-model="partner.ends_on" type="date" required /></label
        ><Button type="submit" label="Создать партнёрство" :loading="op.busy.value" />
      </form>
    </section>
    <p v-for="p in partnerships" :key="p.id">
      {{ institutions.find((i) => i.id === p.school)?.name }} ↔
      {{ institutions.find((i) => i.id === p.university)?.name }} · {{ p.status }}
      <Button
        v-if="session.user?.platform_admin && p.status === 'pending'"
        label="Утвердить"
        text
        @click="run('partnerships/' + p.id + '/transition/', { status: 'active' })"
      /><Button
        v-if="session.user?.platform_admin && p.status === 'active'"
        label="Завершить"
        text
        @click="run('partnerships/' + p.id + '/transition/', { status: 'ended' })"
      />
    </p>
    <h3>Подписки школы</h3>
    <form
      class="form"
      @submit.prevent="run('subscriptions/', { school: subscribeSchool, email_enabled: true })"
    >
      <label
        >Школа<select v-model="subscribeSchool" required>
          <option
            v-for="i in institutions.filter((i) => i.kind === 'school')"
            :key="i.id"
            :value="i.id"
          >
            {{ i.name }}
          </option>
        </select></label
      ><Button type="submit" label="Подписаться" :loading="op.busy.value" />
    </form>
    <p v-for="s in subscriptions" :key="s.id">
      {{ institutions.find((i) => i.id === s.school)?.name }} · Email
      {{ s.email_enabled ? 'включён' : 'отключён' }}
      <Button
        text
        label="Изменить доставку"
        :disabled="op.busy.value"
        @click="run('subscriptions/' + s.id + '/', { email_enabled: !s.email_enabled }, 'PATCH')"
      />
    </p>
    <h3>Групповые заявки</h3>
    <p v-if="!groups.length" class="helper">Нет заявок.</p>
    <article v-for="g in groups" :key="g.id">
      <p>
        {{ workshops.find((w) => w.id === g.workshop)?.title }} · {{ g.status }} · мест
        {{ g.confirmed }}, ожидают {{ g.waiting }}
      </p>
      <Button
        v-if="g.status !== 'cancelled'"
        label="Отменить группу"
        text
        :disabled="op.busy.value"
        @click="cancel('workshop-groups/' + g.id + '/cancel/')"
      />
    </article>
    <h3>Посещаемость</h3>
    <p
      v-for="r in registrations.filter(
        (r) =>
          r.status === 'confirmed' &&
          (session.user?.platform_admin ||
            workshops.some(
              (w) =>
                w.id === r.workshop &&
                (w.organizer === session.user?.id || w.leader === session.user?.id),
            )),
      )"
      :key="r.id"
    >
      {{ workshops.find((w) => w.id === r.workshop)?.title }} · участник {{ r.user }} ·
      {{ r.attended ? 'присутствовал' : 'не отмечен' }}
      <Button
        label="Изменить посещение"
        text
        :disabled="op.busy.value"
        @click="run('registrations/' + r.id + '/attendance/', { attended: !r.attended })"
      />
    </p>
  </section>
</template>
