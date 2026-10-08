<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
const props = defineProps<{ body: string }>()
// Raw HTML is disabled; markdown-it rejects dangerous URL protocols.
const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })
const content = computed(() => markdown.render(props.body))
</script>
<template><div class="article-body" v-html="content" /></template>
<style src="./ArticleBody.css" scoped></style>
