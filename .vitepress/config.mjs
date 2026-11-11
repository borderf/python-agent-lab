import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitepress'
import { learningPaths } from './learning-paths.mjs'

const root = fileURLToPath(new URL('../', import.meta.url))
const repository = 'https://github.com/borderf/python-agent-lab'
const learningRoute = { text: '学习路线', link: '/docs/学习导航' }

function bookSidebar(directory, groups) {
  const files = readdirSync(path.join(root, directory)).filter(name => name.endsWith('.md'))
  const page = name => {
    const content = readFileSync(path.join(root, directory, name), 'utf8')
    const heading = content.match(/^# (.+)$/m)?.[1] ?? name.slice(0, -3)
    return {
      text: heading.replace(/^第\d+章[　\s]*/, ''),
      link: `/${directory}/${name.slice(0, -3)}`
    }
  }
  return [
    learningRoute,
    { text: '教材目录', link: `/${directory}/教材目录` },
    page('00-导读与学习方法.md'),
    ...groups.map(([text, first, last]) => ({
      text,
      collapsed: false,
      items: files.filter(name => /^\d\d-/.test(name))
        .filter(name => Number(name.slice(0, 2)) >= first && Number(name.slice(0, 2)) <= last)
        .sort().map(page)
    })),
    { text: '按需查阅', collapsed: true, items: files.filter(name => name.startsWith('附录') && !name.startsWith('附录G-教材核验')).sort().map(page) }
  ]
}

export default defineConfig({
  lang: 'zh-CN',
  title: 'Python 与 AI 开发',
  description: '从 Java 后端到 Python、AI 应用、Agent、软件架构与产品创业的系统学习教程。',
  base: '/python-agent-lab/',
  srcExclude: ['node_modules/**', '.venv/**', '.pytest_cache/**'],
  rewrites: { 'docs/index.md': 'index.md' },
  lastUpdated: true,
  themeConfig: {
    learningPaths,
    siteTitle: 'Python 与 AI 开发',
    nav: [
      learningRoute,
      { text: 'Python 与 AI', link: '/docs/python-book/教材目录', activeMatch: '/docs/python-book/' },
      { text: '软件架构', link: '/docs/architecture-book/教材目录', activeMatch: '/docs/architecture-book/' },
      { text: '产品与创业', link: '/docs/product-founder-book/教材目录', activeMatch: '/docs/product-founder-book/' }
    ],
    sidebar: {
      '/docs/python-book/': bookSidebar('docs/python-book', [
        ['Python 语言与原理', 1, 12], ['工程与后端服务', 13, 17],
        ['模型、检索、评测与DocPilot', 18, 23], ['受控Agent与恢复', 24, 26], ['可选扩展与求职', 27, 30]
      ]),
      '/docs/architecture-book/': bookSidebar('docs/architecture-book', [
        ['约束与结构', 1, 4], ['数据与协作', 5, 7], ['性能与可靠性', 8, 10], ['演进与实战', 11, 14]
      ]),
      '/docs/product-founder-book/': bookSidebar('docs/product-founder-book', [
        ['问题与研究', 1, 3], ['设计与交付', 4, 6], ['衡量与迭代', 7, 9], ['商业化与创业', 10, 14]
      ]),
      '/': [
        learningRoute,
        { text: '从实验到项目交付', link: '/docs/project-practice/从实验到项目交付' },
        { text: '阶段自测与复习', link: '/docs/python-book/附录H-阶段自测与复习' },
        { text: 'Python 与 AI', link: '/docs/python-book/教材目录' },
        { text: '软件架构', link: '/docs/architecture-book/教材目录' },
        { text: '产品与创业', link: '/docs/product-founder-book/教材目录' },
        { text: '项目规格', link: '/docs/project-practice/项目实践规格' },
        { text: '评测与故障演练', link: '/docs/project-practice/评测与故障演练' },
        { text: '配套练习', link: '/practice/python_ai_course/练习说明' },
        { text: '网站构建与发布', link: '/docs/文档网站使用说明' }
      ]
    },
    outline: { level: [2, 3], label: '本页内容' },
    sidebarMenuLabel: '章节目录',
    outlineTitle: '本页内容',
    returnToTopLabel: '回到顶部',
    darkModeSwitchLabel: '切换深浅模式',
    darkModeSwitchTitle: '切换深色模式',
    lightModeSwitchTitle: '切换浅色模式',
    skipToContentLabel: '跳到正文',
    docFooter: { prev: '全书上一节', next: '全书下一节' },
    lastUpdated: { text: '最后更新' },
    socialLinks: [{ icon: 'github', link: repository }],
    search: {
      provider: 'local',
      options: {
        miniSearch: {
          options: {
            tokenize: text => typeof Intl.Segmenter === 'function'
              ? Array.from(new Intl.Segmenter('zh-CN', { granularity: 'word' }).segment(text))
                .filter(part => part.isWordLike).map(part => part.segment)
              : text.match(/[\p{Script=Han}]|[a-zA-Z0-9_]+/gu) ?? []
          }
        },
        translations: {
          button: { buttonText: '搜索教程', buttonAriaLabel: '搜索教程' },
          modal: { noResultsText: '没有找到相关内容', resetButtonTitle: '清空搜索',
            backButtonTitle: '关闭搜索', displayDetails: '显示搜索摘要',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' } }
        }
      }
    }
  },
  markdown: {
    anchor: {
      // Match the GitHub-style anchors already used by the textbooks.
      slugify: text => text.toLowerCase().replace(/[^\p{L}\p{N}_\- ]/gu, '').replace(/ /g, '-')
    },
    config(md) {
      const fence = md.renderer.rules.fence
      md.renderer.rules.fence = (tokens, index, options, env, renderer) => {
        if (tokens[index].info.trim() === 'mermaid') {
          return `<MermaidDiagram source="${encodeURIComponent(tokens[index].content)}" />`
        }
        return fence(tokens, index, options, env, renderer)
      }

      // Source files stay on GitHub; Markdown chapters stay inside the reading site.
      md.core.ruler.after('inline', 'repository-files', state => {
        const sourceFile = state.env.path
        if (!sourceFile) return
        for (const block of state.tokens) {
          for (const token of block.children ?? []) {
            if (token.type !== 'link_open') continue
            const href = token.attrGet('href')
            if (!href || /^(?:[a-z][a-z\d+.-]*:|\/|#)/i.test(href)) continue
            const [file, fragment] = href.split('#')
            if (!file || file.endsWith('.md')) continue
            const destination = path.resolve(path.dirname(sourceFile), decodeURIComponent(file))
            const relative = path.relative(root, destination).split(path.sep).join('/')
            if (relative.startsWith('../')) continue
            const kind = statSync(destination).isDirectory() ? 'tree' : 'blob'
            token.attrSet('href', `${repository}/${kind}/main/${relative}${fragment ? `#${fragment}` : ''}`)
          }
        }
      })
    }
  }
})
