<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useData, useRoute, withBase } from 'vitepress'
import { readProgress, saveProgress } from './reading-store.mjs'
import { readingState as state } from './reading-state.mjs'

const { theme, page } = useData()
const route = useRoute()
let storage
let timer
const currentPath = computed(() => '/' + page.value.relativePath.replace(/\.md$/, '.html'))
const path = computed(() => theme.value.learningPaths.find(item => item.id === state.value.pathId))
const next = computed(() => {
  const index = path.value?.steps.findIndex(step => step.link === currentPath.value) ?? -1
  return index < 0 ? null : path.value.steps[index + 1]
})
const isRead = computed(() => state.value.read.includes(currentPath.value))
const readCount = computed(() => path.value.steps.filter(step => state.value.read.includes(step.link)).length)

function save() {
  if (storage) saveProgress(storage, state.value)
}

function remember() {
  state.value.last = { path: currentPath.value, title: page.value.title, scroll: window.scrollY }
  save()
}

function scroll() {
  clearTimeout(timer)
  timer = setTimeout(remember, 250)
}

function fontChanged() {
  document.documentElement.style.setProperty('--reading-font-size', `${state.value.font}px`)
  save()
}

function toggleRead() {
  state.value.read = isRead.value ? state.value.read.filter(item => item !== currentPath.value)
    : [...state.value.read, currentPath.value]
  save()
}

onMounted(() => {
  try { storage = window.localStorage; state.value = readProgress(storage) } catch { /* Private storage may be unavailable. */ }
  fontChanged()
  remember()
  window.addEventListener('scroll', scroll, { passive: true })
  window.addEventListener('pagehide', remember)
})
watch(() => route.path, () => {
  clearTimeout(timer)
  // The home page keeps the last lesson's bookmark.
  if (page.value.relativePath !== 'docs/index.md' && page.value.relativePath !== 'index.md') remember()
}, { flush: 'post' })
onUnmounted(() => {
  clearTimeout(timer)
  window.removeEventListener('scroll', scroll)
  window.removeEventListener('pagehide', remember)
})
</script>

<template>
  <nav class="reading-tools" aria-label="学习与阅读设置">
    <div class="reading-settings">
      <label>学习路线
        <select v-model="state.pathId" @change="save">
          <option v-for="item in theme.learningPaths" :key="item.id" :value="item.id">{{ item.label }}</option>
        </select>
      </label>
      <label>字号
        <select v-model.number="state.font" @change="fontChanged">
          <option v-for="size in [16, 17, 19, 21]" :key="size" :value="size">{{ size }}</option>
        </select>
      </label>
      <label class="read-check"><input type="checkbox" :checked="isRead" @change="toggleRead"> 标记已读</label>
    </div>
    <p class="route-progress">{{ path.label }} · 已标记 {{ readCount }} / {{ path.steps.length }} 节。完成练习后再做阶段验收。</p>
    <a v-if="next" :href="withBase(next.link)" class="route-next">按主线继续 → {{ next.title }}</a>
  </nav>
</template>
