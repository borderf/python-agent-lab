<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({ source: { type: String, required: true } })
const diagram = ref('')
const source = decodeURIComponent(props.source)

onMounted(async () => {
  try {
    const { default: mermaid } = await import('mermaid')
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: 'neutral',
      flowchart: { useMaxWidth: false }
    })
    const id = `diagram-${Math.random().toString(36).slice(2)}`
    const result = await mermaid.render(id, source)
    diagram.value = result.svg
  } catch (error) {
    console.error('架构图渲染失败', error)
  }
})
</script>

<template>
  <figure class="mermaid-diagram" aria-label="架构流程图">
    <div v-if="diagram" v-html="diagram" />
    <pre v-else>{{ source }}</pre>
  </figure>
</template>
