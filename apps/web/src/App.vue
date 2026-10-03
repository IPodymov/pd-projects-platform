<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useSession } from '@/stores/session'
import Button from 'primevue/button'
import { useRouter } from 'vue-router'
const session = useSession(),
  router = useRouter(),
  error = ref(''),
  menu = ref(false),
  ready = ref(false),
  loggingOut = ref(false)
function expired() {
  session.user = null
  error.value = 'Сессия истекла. Войдите повторно; введённые данные остаются на странице.'
}
onBeforeUnmount(() => window.removeEventListener('auth-expired', expired))
onMounted(async () => {
  window.addEventListener('auth-expired', expired)
  try {
    await session.refresh()
  } catch (e) {
    error.value = String(e)
  } finally {
    ready.value = true
  }
})
async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await session.logout()
    await router.push('/login')
  } catch (e) {
    error.value = String(e)
  } finally {
    loggingOut.value = false
  }
}
const links = [
  ['/', 'Обзор', 'pi-home'],
  ['/manage/courses', 'Курсы', 'pi-book'],
  ['/manage/projects', 'Проекты', 'pi-folder'],
  ['/schedule', 'Расписание', 'pi-calendar'],
  ['/workshops', 'Мастер-классы', 'pi-sparkles'],
  ['/manage/publications', 'Журнал', 'pi-file'],
  ['/manage/competitions', 'Конкурсы', 'pi-trophy'],
]
</script>
<template>
  <div class="app-shell">
    <aside :class="{ open: menu }">
      <RouterLink to="/" class="brand"
        ><span class="brand-mark">и<span>б</span></span
        ><span>Инженеры<br /><strong>будущего</strong></span></RouterLink
      >
      <p class="nav-caption">ОБРАЗОВАТЕЛЬНАЯ ПЛАТФОРМА</p>
      <nav @click="menu = false">
        <RouterLink
          v-for="[path, title, icon] in links"
          :key="path"
          :to="path || '/'"
          :exact-active-class="'selected'"
          ><i :class="'pi ' + icon" />{{ title }}</RouterLink
        >
        <template v-if="session.staff"
          ><p class="nav-caption">УПРАВЛЕНИЕ</p>
          <RouterLink to="/classes"><i class="pi pi-users" />Классы и приглашения</RouterLink
          ><RouterLink to="/crm"><i class="pi pi-chart-bar" />Результаты · CRM</RouterLink
          ><RouterLink to="/manage/institutions"><i class="pi pi-building" />Учреждения</RouterLink
          ><RouterLink to="/manage/classrooms"
            ><i class="pi pi-th-large" />Учебные группы</RouterLink
          ><RouterLink v-if="session.institutionAdmin" to="/manage/invitations"
            ><i class="pi pi-envelope" />Пригласить сотрудника</RouterLink
          ></template
        >
      </nav>
      <div class="sidebar-note">
        <span class="tag">УЧИМСЯ СОЗДАВАТЬ</span>
        <p>От первой идеи<br />к инженерному проекту.</p>
        <span class="note-orbit">↗</span>
      </div>
    </aside>
    <div class="workspace">
      <header>
        <button class="mobile-menu" aria-label="Открыть навигацию" @click="menu = !menu">
          <i class="pi pi-bars" /></button
        ><span class="header-label"
          >Проектная деятельность <span class="separator">/</span> Личный кабинет</span
        >
        <div class="header-profile">
          <span v-if="session.user?.id" class="avatar">{{
            session.user.name?.slice(0, 1) || 'У'
          }}</span
          ><RouterLink v-if="session.user?.id" to="/account">{{
            session.user.name || session.user.email
          }}</RouterLink
          ><span v-else>Гость</span
          ><Button
            v-if="session.user?.id"
            icon="pi pi-sign-out"
            text
            aria-label="Выйти"
            :loading="loggingOut"
            @click="logout"
          /><RouterLink v-else to="/login">Войти →</RouterLink>
        </div>
      </header>
      <main>
        <div v-if="error" class="state error" role="alert">{{ error }}</div>
        <RouterView :key="$route.path" v-if="ready" />
        <div v-else class="state" role="status">Загружаем кабинет…</div>
      </main>
      <footer>Инженеры будущего <span>Платформа проектного обучения</span></footer>
    </div>
  </div>
</template>
