import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
function bookChapters(book) {
  const folder = path.join(root, 'docs', book)
  return Object.fromEntries(readdirSync(folder).filter(name => /^\d\d-/.test(name)).sort().map(name => {
    const heading = readFileSync(path.join(folder, name), 'utf8').match(/^# (.+)$/m)[1]
    return [Number(name.slice(0, 2)), { title: heading, link: `/docs/${book}/${name.slice(0, -3)}.html` }]
  }))
}
const chapters = bookChapters('python-book')
const bookSteps = book => Object.entries(bookChapters(book)).filter(([number]) => Number(number) > 0).map(([, step]) => step)
const foundation = Array.from({ length: 17 }, (_, index) => index + 1)
const application = [...foundation, 18, 19, 20, 21, 26, 27]

export const learningPaths = [
  { id: 'python', label: 'Python 基础', steps: foundation.slice(0, 12).map(number => chapters[number]) },
  { id: 'application', label: 'AI 应用交付', steps: [...application, 29, 30].map(number => chapters[number]) },
  { id: 'agent', label: 'Agent 开发', steps: [...application, 22, 23, 28, 29, 30].map(number => chapters[number]) },
  { id: 'architecture', label: '软件架构', steps: bookSteps('architecture-book') },
  { id: 'product', label: '产品与创业', steps: bookSteps('product-founder-book') }
]
