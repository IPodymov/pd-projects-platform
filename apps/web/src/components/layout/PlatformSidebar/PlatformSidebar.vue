<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '@/stores/session'
import { errorMessage } from '@/utils/errors'
const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const session = useSession()
const router = useRouter()
const loggingOut = ref(false)
const logoutError = ref('')
async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  logoutError.value = ''
  try {
    await session.logout()
    await router.replace('/login')
    emit('close')
  } catch (error) {
    logoutError.value = errorMessage(error)
  } finally {
    loggingOut.value = false
  }
}
const role = computed(() =>
  session.user?.platform_admin
    ? 'Администратор'
    : session.institutionAdmin
      ? 'Администратор учреждения'
      : session.user?.roles.includes('curator')
        ? 'Куратор ПД'
        : session.staff
          ? 'Преподаватель'
          : session.user?.id
            ? 'Ученик'
            : 'Гость',
)
const links = computed(() => [
  { to: '/', label: 'Обзор' },
  ...(session.staff ? [{ to: '/classes', label: 'Классы и ученики' }] : []),
  { to: '/manage/projects', label: session.staff ? 'Проверка проектов' : 'Мои проекты' },
  { to: '/manage/courses', label: 'Курсы' },
  { to: '/workshops', label: 'Мастер-классы' },
  { to: '/schedule', label: 'Расписание' },
  { to: '/manage/publications', label: session.staff ? 'Блог' : 'Блог и материалы' },
  { to: '/manage/competitions', label: 'Конкурсы' },
  ...(session.institutionAdmin
    ? [
        { to: '/manage/users', label: 'Учётные записи' },
        { to: '/manage/institutions', label: 'Школы и сотрудники' },
        { to: '/manage/invitations', label: 'Пригласить сотрудника' },
      ]
    : []),
  ...(session.staff ? [{ to: '/crm', label: 'Результаты обучения' }] : []),
])
</script>
<template>
  <button
    v-if="props.open"
    class="sidebar-overlay"
    aria-label="Закрыть меню"
    @click="emit('close')"
  />
  <aside class="platform-sidebar" :class="{ 'is-open': open }" aria-label="Главная навигация">
    <RouterLink to="/" class="platform-brand" @click="emit('close')">Проектория</RouterLink>
    <nav class="platform-nav">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        :class="{
          selected:
            $route.path === link.to ||
            (link.to === '/manage/projects' && $route.path.startsWith('/projects/')) ||
            (link.to === '/manage/courses' && $route.path.startsWith('/courses/')) ||
            (link.to === '/manage/publications' &&
              ($route.path.startsWith('/articles/') || $route.path.startsWith('/blog/'))),
        }"
        @click="emit('close')"
        >{{ link.label }}</RouterLink
      >
    </nav>
    <div class="sidebar-profile">
      <strong>{{ role }}</strong>
      <RouterLink v-if="session.user?.id" to="/account" @click="emit('close')">{{
        session.user.name || session.user.email
      }}</RouterLink>
      <RouterLink v-else to="/login" @click="emit('close')">Войти в аккаунт</RouterLink>
      <button
        v-if="session.user?.id"
        type="button"
        class="sidebar-logout"
        :disabled="loggingOut"
        @click="logout"
      >
        <i class="pi pi-sign-out" aria-hidden="true" />
        {{ loggingOut ? 'Выходим…' : 'Выйти из аккаунта' }}
      </button>
      <p v-if="logoutError" class="sidebar-logout-error" role="alert">{{ logoutError }}</p>
    </div>
  </aside>
</template>
<style src="./PlatformSidebar.css" scoped></style>
