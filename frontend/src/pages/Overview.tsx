import { Link } from 'react-router-dom'
import {
  IconArrowRight,
  IconChart,
  IconClipboard,
  IconDatabase,
  IconDocument,
  IconFlask,
  IconLightbulb,
  IconLock,
  IconMessage,
  IconSearch,
  IconSend,
  IconShield,
  IconTarget,
} from '../components/icons'

const TASKS = [
  {
    theme: 'blue' as const,
    title: '我有一个科研问题',
    example: '根系损伤后 Streptomyces 增加可能意味着什么？',
    icon: IconMessage,
    items: [
      { icon: IconSearch, text: '检索相关研究' },
      { icon: IconDocument, text: '整合天然产物证据' },
      { icon: IconLightbulb, text: '判断证据边界' },
      { icon: IconMessage, text: '生成带来源的回答' },
    ],
    to: '/ask',
    action: '进入科研问答',
  },
  {
    theme: 'teal' as const,
    title: '我有一个实验结果',
    example: 'Streptomyces 与 M1023 显著正相关，r = 0.72',
    icon: IconFlask,
    items: [
      { icon: IconTarget, text: '解释实验发现' },
      { icon: IconDocument, text: '查找相关文献' },
      { icon: IconClipboard, text: '检查天然产物记录' },
      { icon: IconShield, text: '判断是否存在过度外推' },
      { icon: IconSend, text: '给出下一步验证建议' },
    ],
    to: '/results',
    action: '进入结果解释',
  },
]

const FEATURES = [
  { icon: IconShield, title: '证据优先', desc: '严格证据分级与引用' },
  { icon: IconDatabase, title: '多源整合', desc: '文献、数据库、代谢物' },
  { icon: IconChart, title: '透明可追溯', desc: '完整推理过程记录' },
  { icon: IconLock, title: '安全合规', desc: '数据隐私与合规保障' },
]

function HeroDecorations() {
  return (
    <div className="home-decorations" aria-hidden="true">
      <svg className="home-deco home-deco--dna" viewBox="0 0 120 200" fill="none">
        <path
          d="M30 10 C70 30, 50 70, 90 90 S50 150, 70 190"
          stroke="currentColor"
          strokeWidth="2"
          opacity="0.35"
        />
        <path
          d="M90 10 C50 30, 70 70, 30 90 S70 150, 50 190"
          stroke="currentColor"
          strokeWidth="2"
          opacity="0.35"
        />
        {Array.from({ length: 8 }).map((_, i) => (
          <line
            key={i}
            x1={30 + (i % 2) * 60}
            y1={20 + i * 22}
            x2={90 - (i % 2) * 60}
            y2={20 + i * 22}
            stroke="currentColor"
            strokeWidth="1.5"
            opacity="0.25"
          />
        ))}
      </svg>
      <svg className="home-deco home-deco--molecule" viewBox="0 0 80 80" fill="none">
        <circle cx="40" cy="40" r="6" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="20" cy="25" r="4" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="60" cy="25" r="4" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="20" cy="58" r="4" stroke="currentColor" strokeWidth="1.5" />
        <line x1="40" y1="40" x2="20" y2="25" stroke="currentColor" strokeWidth="1.25" />
        <line x1="40" y1="40" x2="60" y2="25" stroke="currentColor" strokeWidth="1.25" />
        <line x1="40" y1="40" x2="20" y2="58" stroke="currentColor" strokeWidth="1.25" />
      </svg>
      <svg className="home-deco home-deco--plant" viewBox="0 0 64 80" fill="none">
        <ellipse cx="32" cy="72" rx="22" ry="6" fill="#8B6914" opacity="0.35" />
        <path d="M32 72 V38" stroke="#2d8a4e" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M32 52 C18 48, 14 34, 22 28" stroke="#3cb371" strokeWidth="2" fill="none" />
        <path d="M32 44 C46 40, 50 26, 42 20" stroke="#3cb371" strokeWidth="2" fill="none" />
        <ellipse cx="20" cy="28" rx="8" ry="5" fill="#4caf6e" opacity="0.7" transform="rotate(-30 20 28)" />
        <ellipse cx="44" cy="20" rx="8" ry="5" fill="#4caf6e" opacity="0.7" transform="rotate(30 44 20)" />
      </svg>
    </div>
  )
}

export function OverviewPage() {
  return (
    <div className="home-page">
      <section className="home-hero">
        <HeroDecorations />
        <h1 className="home-title">
          <span className="home-title-rhizonp">RhizoNP</span>{' '}
          <span className="home-title-navigator">Navigator</span>
        </h1>
        <p className="home-subtitle">
          面向微生物–代谢物与天然产物研究的证据约束科研辅助工具
        </p>
      </section>

      <section className="task-grid" aria-label="核心任务入口">
        {TASKS.map((task) => {
          const CardIcon = task.icon
          return (
            <article key={task.to} className={`task-card task-card--${task.theme}`}>
              <div className="task-card-header">
                <span className={`task-card-icon task-card-icon--${task.theme}`}>
                  <CardIcon size={22} />
                </span>
                <h2>{task.title}</h2>
              </div>
              <p className="task-example">“{task.example}”</p>
              <ul className="task-features">
                {task.items.map(({ icon: ItemIcon, text }) => (
                  <li key={text}>
                    <ItemIcon size={18} />
                    <span>{text}</span>
                  </li>
                ))}
              </ul>
              <Link to={task.to} className={`task-btn task-btn--${task.theme}`}>
                {task.action}
                <IconArrowRight size={18} />
              </Link>
            </article>
          )
        })}
      </section>

      <section className="feature-bar" aria-label="平台特性">
        {FEATURES.map(({ icon: FeatureIcon, title, desc }) => (
          <div key={title} className="feature-bar-item">
            <span className="feature-bar-icon">
              <FeatureIcon size={22} />
            </span>
            <div>
              <strong>{title}</strong>
              <span>{desc}</span>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}
