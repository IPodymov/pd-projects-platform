<script setup lang="ts">
import { fieldLabel } from '@/utils/errors'
defineProps<{ error?: string; fields?: Record<string, string[]>; success?: string }>()
</script>
<template>
  <div v-if="error" class="state error" role="alert">
    <p>{{ error }}</p>
    <ul v-if="fields && Object.keys(fields).length">
      <li v-for="(messages, key) in fields" :key="key">
        {{ fieldLabel(String(key)) }}: {{ messages.join(' · ') }}
      </li>
    </ul>
  </div>
  <p v-if="success" class="helper" role="status">{{ success }}</p>
</template>
