<script setup>
import { computed } from 'vue'
import { useData, withBase } from 'vitepress'
import { readingState } from './reading-state.mjs'

const { page, theme } = useData()
const next = computed(() => {
  const steps = theme.value.learningPaths.find(path => path.id === readingState.value.pathId).steps
  const current = '/' + page.value.relativePath.replace(/\.md$/, '.html')
  const index = steps.findIndex(step => step.link === current)
  return index < 0 ? null : steps[index + 1]
})
</script>

<template>
  <nav v-if="next" class="reading-next" aria-label="按学习主线继续">
    <p>完成本节练习后，继续所选路线</p>
    <a :href="withBase(next.link)">下一步 → {{ next.title }}</a>
  </nav>
</template>
