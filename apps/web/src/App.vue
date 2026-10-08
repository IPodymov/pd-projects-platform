<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useSession } from '@/stores/session'
import { errorMessage } from '@/utils/errors'
import PlatformLayout from '@/components/layout/PlatformLayout/PlatformLayout.vue'
import AuthLayout from '@/components/auth/AuthLayout/AuthLayout.vue'
const session = useSession(),
  route = useRoute(),
  ready = ref(false),
  error = ref('')
const layout = computed(() => (route.meta.layout === 'auth' ? AuthLayout : PlatformLayout))
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
    error.value = errorMessage(e)
  } finally {
    ready.value = true
  }
})
</script>
<template>
  <a class="skip-link" href="#main-content">Перейти к содержимому</a>
  <component :is="layout"
    ><div v-if="error" class="state error" role="alert">{{ error }}</div>
    <RouterView :key="$route.path" v-if="ready" />
    <div v-else class="state" role="status">Загрузка платформы…</div></component
  >
</template>
<style src="./App.css"></style>
