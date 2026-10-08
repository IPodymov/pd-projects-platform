import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { client, api, setCsrf } from '@/api'
import type { components } from '@future/api-client'
export const useSession = defineStore('session', () => {
  const user = ref<components['schemas']['Session'] | null>(null)
  const staff = computed(() => !!user.value?.platform_admin || !!user.value?.roles.length)
  const institutionAdmin = computed(
    () => !!user.value?.platform_admin || !!user.value?.roles.includes('admin'),
  )
  const managesSchedule = computed(
    () => institutionAdmin.value || !!user.value?.roles.includes('curator'),
  )
  const managesCourses = computed(
    () => managesSchedule.value || !!user.value?.roles.includes('teacher'),
  )
  async function refresh() {
    const result = await client.GET('/api/v1/session/')
    if (!result.data) throw new Error('Не удалось загрузить сессию')
    user.value = result.data
    setCsrf(result.data.csrf)
  }
  async function login(email: string, password: string) {
    await api('login/', 'POST', { email, password })
    await refresh()
  }
  async function logout() {
    await api('logout/', 'POST')
    await refresh()
  }
  return { user, staff, institutionAdmin, managesSchedule, managesCourses, refresh, login, logout }
})
