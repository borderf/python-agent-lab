export const storageKey = 'python-agent-lab:reading:v1'

function isLessonPath(value) {
  return typeof value === 'string' && /^\/(docs|practice)\/.+\.html$/.test(value)
    && !value.includes('..') && !/[?#\\]/.test(value)
}

export function readProgress(storage) {
  const empty = { version: 1, pathId: 'application', font: 17, read: [], last: null }
  try {
    const value = JSON.parse(storage.getItem(storageKey))
    if (!value || value.version !== 1) return empty
    const last = value.last
    return {
      ...empty,
      pathId: ['python', 'application', 'agent', 'architecture', 'product'].includes(value.pathId) ? value.pathId : empty.pathId,
      font: [16, 17, 19, 21].includes(value.font) ? value.font : empty.font,
      read: Array.isArray(value.read) ? [...new Set(value.read.filter(isLessonPath))] : [],
      last: last && isLessonPath(last.path) && typeof last.title === 'string'
        && Number.isFinite(last.scroll) && last.scroll >= 0 ? last : null
    }
  } catch {
    return empty
  }
}

export function saveProgress(storage, value) {
  try {
    storage.setItem(storageKey, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}
