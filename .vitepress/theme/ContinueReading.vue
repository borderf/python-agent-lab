<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRouter, withBase } from 'vitepress'
import { readProgress } from './reading-store.mjs'

const router = useRouter()
const last = ref(null)
onMounted(() => {
  try { last.value = readProgress(window.localStorage).last } catch { /* Reading works without storage. */ }
})
async function resume() {
  const bookmark = last.value
  await router.go(withBase(bookmark.path))
  await nextTick()
  window.requestAnimationFrame(() => window.scrollTo({ top: bookmark.scroll, behavior: 'instant' }))
}
</script>

<template>
  <section v-if="last" class="continue-reading" aria-label="继续上次阅读">
    <p>上次读到 {{ last.title }}</p>
    <button type="button" @click="resume">继续上次阅读 →</button>
    <span>阅读位置保存在当前浏览器</span>
  </section>
</template>
