import { ref } from 'vue'

// Shared by the controls and the chapter-end navigation in this browser session.
export const readingState = ref({ pathId: 'application', font: 17, read: [] })
