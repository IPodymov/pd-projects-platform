<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Button from 'primevue/button'
import { api } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import { errorMessage } from '@/utils/errors'
import PageState from '@/components/common/PageState/PageState.vue'
import FormFeedback from '@/components/common/FormFeedback/FormFeedback.vue'
import InstitutionTable from '@/components/institutions/InstitutionTable/InstitutionTable.vue'
import InstitutionStaff from '@/components/institutions/InstitutionStaff/InstitutionStaff.vue'
import type { components } from '@future/api-client'
const session = useSession(),
  op = useOperation(),
  loading = ref(true),
  error = ref(''),
  showForm = ref(false)
const institutions = ref<components['schemas']['Institution'][]>([]),
  classes = ref<components['schemas']['Classroom'][]>([]),
  staff = ref<components['schemas']['Staff'][]>([]),
  members = ref<components['schemas']['Membership'][]>([])
const form = ref({ name: '', kind: 'school' })
const teachers = computed(() => staff.value.filter((s) => s.active && s.role === 'teacher')),
  curators = computed(() => staff.value.filter((s) => s.active && s.role === 'curator'))
const students = computed(
  () => new Set(members.value.filter((m) => !m.ended_at).map((m) => m.user)).size,
)
async function load() {
  loading.value = true
  error.value = ''
  try {
    ;[institutions.value, classes.value, staff.value, members.value] = await Promise.all([
      api<components['schemas']['Institution'][]>('institutions/'),
      api<components['schemas']['Classroom'][]>('classrooms/'),
      api<components['schemas']['Staff'][]>('staff/'),
      api<components['schemas']['Membership'][]>('memberships/'),
    ])
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
async function create() {
  await op.execute(async () => {
    await api('institutions/', 'POST', form.value)
    form.value = { name: '', kind: 'school' }
    showForm.value = false
    await load()
  }, 'Учреждение добавлено')
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">Администрирование</p>
      <h1>Учреждения и сотрудники</h1>
      <p class="subtitle">Классы, преподаватели и кураторы проекта</p>
    </div>
    <Button
      v-if="session.user?.platform_admin"
      label="Добавить учреждение"
      icon="pi pi-plus"
      @click="showForm = !showForm"
    />
  </div>
  <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
  <form v-if="showForm" class="panel form institution-form" @submit.prevent="create">
    <label>Название<input v-model="form.name" required maxlength="200" /></label
    ><label
      >Тип<select v-model="form.kind">
        <option value="school">Школа</option>
        <option value="college">Колледж</option>
        <option value="university">Вуз</option>
      </select></label
    ><Button label="Сохранить" type="submit" :loading="op.busy.value" />
  </form>
  <PageState :loading="loading" :error="error" @retry="load"
    ><div class="institution-stats">
      <div>
        <span>Учреждения</span><strong>{{ institutions.length }}</strong>
      </div>
      <div>
        <span>Преподаватели</span><strong>{{ new Set(teachers.map((t) => t.user)).size }}</strong>
      </div>
      <div>
        <span>Кураторы</span><strong>{{ new Set(curators.map((c) => c.user)).size }}</strong>
      </div>
      <div>
        <span>Учащиеся</span><strong>{{ students }}</strong>
      </div>
    </div>
    <div class="institutions-workspace">
      <InstitutionTable
        :institutions="institutions"
        :classes="classes"
        :staff="staff"
        :members="members"
      />
      <aside>
        <InstitutionStaff
          title="Преподаватели"
          :staff="teachers"
          :institutions="institutions"
        /><InstitutionStaff title="Кураторы" :staff="curators" :institutions="institutions" />
      </aside></div
  ></PageState>
</template>
<style src="./InstitutionsView.css" scoped></style>
