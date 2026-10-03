<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import Button from 'primevue/button'
import ClassManagement from '@/components/ClassManagement.vue'
import PageState from '@/components/PageState.vue'
import { api, downloadUrl } from '@/api'
import type { components } from '@future/api-client'
type Classroom = components['schemas']['Classroom']
type Prospect = components['schemas']['Prospect']
type Batch = Omit<components['schemas']['Import'], 'rows' | 'errors'> & {
  rows: { row: number; full_name: string; email: string; existing: boolean }[]
  errors: { row: number; reason: string }[]
}
const classes = ref<Classroom[]>([]),
  prospects = ref<Prospect[]>([]),
  selected = ref(''),
  batch = ref<Batch | null>(null),
  file = ref<File>(),
  error = ref(''),
  loading = ref(true),
  busy = ref(false),
  message = ref('')
const visible = computed(() => prospects.value.filter((p) => p.classroom === selected.value))
async function load() {
  loading.value = true
  error.value = ''
  try {
    ;[classes.value, prospects.value] = await Promise.all([
      api<Classroom[]>('classrooms/'),
      api<Prospect[]>('prospects/'),
    ])
    if (!selected.value) selected.value = classes.value[0]?.id || ''
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
function pick(e: Event) {
  file.value = (e.target as HTMLInputElement).files?.[0]
}
async function preview() {
  if (busy.value || !file.value || !selected.value) return
  busy.value = true
  error.value = ''
  try {
    const data = new FormData()
    data.append('classroom', selected.value)
    data.append('file', file.value)
    batch.value = await api<Batch>('imports/preview/', 'POST', data)
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}
async function apply() {
  if (busy.value || !batch.value) return
  busy.value = true
  try {
    const r = await api<{ created: number; skipped: number }>(
      'imports/' + batch.value.id + '/apply/',
      'POST',
    )
    message.value = `Создано: ${r.created}, пропущено: ${r.skipped}`
    batch.value = null
    await load()
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}
const edit = ref(''),
  newEmail = ref('')
function editEmail(id: string, email: string) {
  edit.value = id
  newEmail.value = email
}
async function correct() {
  if (busy.value) return
  busy.value = true
  try {
    await api('prospects/' + edit.value + '/correct_email/', 'POST', { email: newEmail.value })
    edit.value = ''
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
      <p class="eyebrow">ОБРАЗОВАТЕЛЬНАЯ РАБОТА</p>
      <h1>Классы и приглашения</h1>
      <p class="subtitle">Пригласите учеников и помогите им начать.</p>
    </div>
  </div>
  <PageState :loading="loading" :error="error" @retry="load"
    ><div class="filters">
      <select v-model="selected" aria-label="Выберите класс" @change="batch = null">
        <option v-for="cl in classes" :key="cl.id" :value="cl.id">
          {{ cl.institution_name }} · {{ cl.name }} · {{ cl.academic_year }}
        </option>
      </select>
    </div>
    <div class="panel">
      <h2>Импорт учащихся</h2>
      <p class="helper">
        CSV или XLSX · колонки «ФИО» и «email» · до 500 строк и 2 МБ. Сначала проверка, затем
        подтверждение.
      </p>
      <div class="actions">
        <input type="file" accept=".csv,.xlsx" aria-label="Файл учащихся" @change="pick" /><Button
          label="Предпросмотр"
          :disabled="!file || !selected"
          :loading="busy"
          @click="preview"
        /><a :href="downloadUrl('import-template/')">Скачать шаблон ↓</a
        ><a v-if="selected" :href="downloadUrl('classrooms/' + selected + '/export/')"
          >Экспорт приглашений XLSX ↓</a
        >
      </div>
    </div>
    <div v-if="batch" class="panel" style="margin-top: 22px">
      <h2>Предварительная проверка</h2>
      <p>{{ batch.rows.length }} строк · {{ batch.errors.length }} ошибок</p>
      <pre v-if="batch.errors.length" class="error">{{
        JSON.stringify(batch.errors, null, 2)
      }}</pre>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Строка</th>
              <th>ФИО</th>
              <th>Email</th>
              <th>Существующая запись</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(r, i) in batch.rows as {
                row: number
                full_name: string
                email: string
                existing: boolean
              }[]"
              :key="i"
            >
              <td>{{ r.row }}</td>
              <td>{{ r.full_name }}</td>
              <td>{{ r.email }}</td>
              <td>{{ r.existing ? 'Да, будет пропущена' : 'Нет' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <Button
        label="Подтвердить импорт и приглашения"
        :disabled="!!batch.errors.length"
        :loading="busy"
        @click="apply"
      />
    </div>
    <p v-if="message" class="success">{{ message }}</p>
    <div class="section-heading"><h2>Будущие и зарегистрированные участники</h2></div>
    <div class="panel table-wrap">
      <table>
        <thead>
          <tr>
            <th>ФИО</th>
            <th>Email</th>
            <th>Регистрация</th>
            <th>Действие</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in visible" :key="p.id">
            <td>{{ p.full_name }}</td>
            <td>{{ p.email }}</td>
            <td>
              <span class="badge">{{ p.user ? 'Зарегистрирован' : 'Приглашён' }}</span>
            </td>
            <td>
              <Button
                v-if="!p.user"
                label="Исправить почту"
                text
                @click="editEmail(p.id, p.email)"
              />
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!visible.length" class="helper">Учащиеся ещё не импортированы.</p>
    </div>
    <form v-if="edit" class="panel form" style="margin-top: 22px" @submit.prevent="correct">
      <label>Исправленный email<input v-model="newEmail" type="email" required /></label>
      <p class="helper">
        Старая ссылка и коды будут отозваны. На новый адрес отправится новое приглашение.
      </p>
      <Button type="submit" label="Исправить и перевыпустить" /></form
  ></PageState>
  <ClassManagement v-if="selected" :classroom="selected" />
</template>
