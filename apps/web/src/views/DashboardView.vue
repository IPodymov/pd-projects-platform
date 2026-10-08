<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import PageState from '@/components/common/PageState/PageState.vue'
import { useSession } from '@/stores/session'
import { api } from '@/api'
import type { components } from '@future/api-client'
type Project = components['schemas']['Project']
type Lesson = components['schemas']['Lesson']
type Notification = components['schemas']['Notification']
const session = useSession(),
  projects = ref<Project[]>([]),
  lessons = ref<Lesson[]>([]),
  notifications = ref<Notification[]>([]),
  loading = ref(true),
  error = ref(''),
  busy = ref(false)
async function load() {
  loading.value = true
  error.value = ''
  try {
    await session.refresh()
    if (session.user?.id) {
      ;[projects.value, lessons.value, notifications.value] = await Promise.all([
        api<Project[]>('projects/'),
        api<Lesson[]>('lessons/'),
        api<Notification[]>('notifications/'),
      ])
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
async function markRead(id: string) {
  if (busy.value) return
  busy.value = true
  try {
    await api('notifications/' + id + '/read/', 'POST')
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">ЛИЧНЫЙ КАБИНЕТ</p>
      <h1>
        {{ session.user?.name ? 'Здравствуйте, ' + session.user.name : 'Место, где идеи растут' }}
      </h1>
      <p class="subtitle">Проектируйте, пробуйте и создавайте будущее.</p>
    </div>
    <span class="badge">ПРОЕКТНОЕ ОБУЧЕНИЕ</span>
  </div>
  <section class="hero">
    <div>
      <span class="tag">ОТ ИДЕИ К РЕЗУЛЬТАТУ</span>
      <h2 data-layout="dashboardview-style-1">Большие открытия<br />начинаются с вашей идеи.</h2>
      <p>
        Учебные материалы, команда и обратная связь — всё для подготовки к конкурсу «Инженеры
        будущего».
      </p>
      <RouterLink :to="session.user?.id ? '/manage/projects' : '/login'"
        ><Button
          :label="session.user?.id ? 'К моим проектам' : 'Войти в платформу'"
          icon="pi pi-arrow-up-right"
          icon-pos="right"
      /></RouterLink>
    </div>
    <div class="hero-art" aria-hidden="true">
      <div class="orbit" />
      <div class="orbit" />
      <div class="core">↗</div>
      <div class="dot" />
    </div>
  </section>
  <PageState :loading="loading" :error="error" @retry="load"
    ><template v-if="session.user?.id"
      ><div class="grid">
        <div class="panel stat">
          <span class="stat-label">Доступные проекты</span>
          <div class="stat-value">{{ projects.length }}</div>
          <span class="helper">Ваши команды и назначенные классы</span>
        </div>
        <div class="panel stat">
          <span class="stat-label">Предстоящие занятия</span>
          <div class="stat-value">
            {{
              lessons.filter((l) => new Date(l.starts_at) > new Date() && l.status !== 'cancelled')
                .length
            }}
          </div>
          <RouterLink to="/schedule" class="helper">Открыть расписание →</RouterLink>
        </div>
        <div class="panel stat">
          <span class="stat-label">Непрочитанные уведомления</span>
          <div class="stat-value">{{ notifications.filter((n) => !n.read_at).length }}</div>
          <span class="helper">Изменения занятий и мастер-классов</span>
        </div>
      </div>
      <div class="section-heading">
        <h2>Ваши проекты</h2>
        <RouterLink to="/manage/projects" class="helper">Все проекты →</RouterLink>
      </div>
      <PageState :empty="!projects.length"
        ><div class="grid">
          <RouterLink
            v-for="p in projects.slice(0, 3)"
            :key="p.id"
            :to="'/projects/' + p.id"
            class="panel"
            ><div class="card-icon"><i class="pi pi-folder" /></div>
            <h3>{{ p.title }}</h3>
            <p class="helper">{{ p.description || 'Описание ещё не добавлено' }}</p>
            <div class="card-meta">
              <span>{{ p.classroom_name }}</span
              ><span>{{ p.members.length }} участников</span>
            </div>
            <div class="progress"><span :style="{ width: p.progress + '%' }" /></div>
            <div class="card-foot">
              <span>Принятые задания · {{ p.progress }}%</span><span>Открыть ↗</span>
            </div></RouterLink
          >
        </div></PageState
      >
      <div class="section-heading"><h2>Последние уведомления</h2></div>
      <div class="panel">
        <p v-if="!notifications.length" class="helper">Новых уведомлений пока нет.</p>
        <div v-for="n in notifications.slice(0, 8)" :key="n.id" class="card-foot">
          <span
            >{{ n.title }}<small class="helper"> · Email: {{ n.delivery_status }}</small></span
          ><Button
            v-if="!n.read_at"
            label="Прочитано"
            text
            :disabled="busy"
            @click="markRead(n.id)"
          />
        </div></div
    ></template>
    <p v-else class="subtitle">
      Войдите по приглашению, чтобы увидеть свои занятия, проекты и результаты.
    </p></PageState
  >
</template>
<style src="./DashboardView.css" scoped></style>
