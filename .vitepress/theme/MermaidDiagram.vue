<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({ source: { type: String, required: true } })
const diagram = ref('')
const source = computed(() => decodeURIComponent(props.source))
const host = ref(null)
const dialog = ref(null)
const expanded = ref(false)
const failed = ref(false)
let observer
let visible = false
let revision = 0

async function render() {
  const current = ++revision
  failed.value = false
  try {
    const { default: mermaid } = await import('mermaid')
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: 'neutral',
      flowchart: { useMaxWidth: false }
    })
    const id = `diagram-${Math.random().toString(36).slice(2)}`
    const result = await mermaid.render(id, source.value)
    if (current === revision) diagram.value = result.svg
  } catch (error) {
    if (current === revision) failed.value = true
  }
}

async function enlarge() {
  expanded.value = true
  await nextTick()
  dialog.value.showModal()
}

onMounted(() => {
  if (!('IntersectionObserver' in window)) { visible = true; render(); return }
  observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      visible = true
      observer.disconnect()
      render()
    }
  }, { rootMargin: '240px' })
  observer.observe(host.value)
})
watch(source, () => { diagram.value = ''; if (visible) render() })
onUnmounted(() => { revision += 1; observer?.disconnect() })
</script>

<template>
  <figure ref="host" class="mermaid-diagram" aria-label="架构流程图">
    <button v-if="diagram" type="button" class="diagram-expand" @click="enlarge">放大查看流程图</button>
    <div v-if="diagram && !expanded" class="diagram-canvas" v-html="diagram" />
    <p v-else-if="!diagram" role="status">{{ failed ? '流程图加载失败，可以重试或查看源码。' : '正在准备流程图…' }}</p>
    <button v-if="failed" type="button" @click="render">重试加载</button>
    <details v-if="failed"><summary>查看流程图源码</summary><pre>{{ source }}</pre></details>
    <dialog ref="dialog" class="diagram-dialog" aria-label="放大的架构流程图" @close="expanded = false">
      <button type="button" autofocus @click="dialog.close()">关闭流程图</button>
      <div v-if="expanded" class="diagram-canvas" v-html="diagram" />
    </dialog>
  </figure>
</template>
