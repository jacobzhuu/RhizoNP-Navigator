import { Link } from 'react-router-dom'

const FLOW_STEPS = [
  '科学查询 / 组学数据',
  '文献检索',
  '分类学感知证据分级',
  '天然产物候选关联',
  '证据约束科学报告',
]

const CAPABILITIES = [
  {
    title: '文献检索',
    description: '对索引文献片段进行 BM25、稠密向量、混合及重排序检索，并保留溯源轨迹。',
    scope: '有界语料索引，非 PubMed 全库检索。',
    link: '/literature',
  },
  {
    title: '分类学感知分级',
    description: '根据查询分类单元与文献分类单元之间的分类学距离，评估证据强度。',
    scope: '基于规则策略；属级 16S 不能支持菌株级主张。',
    link: '/evidence-grader',
  },
  {
    title: '天然产物关联',
    description: '按分类学距离、化合物匹配和证据等级对候选化合物排序。',
    scope: 'bounded NPAtlas 快照与本地 fixture 记录。',
    link: '/natural-products',
  },
  {
    title: '自有数据流程',
    description: '将组学关联 CSV 经分级与候选关联处理，可选文献检索桥接。',
    scope: '需指定数据目录；当前不支持浏览器上传。',
    link: '/own-data',
  },
  {
    title: '证据约束报告',
    description: '生成有证据边界约束的回答，含主张、引用与验证建议。',
    scope: '可选大模型写作；校验失败时回退确定性写作器。',
    link: '/grounded-report',
  },
  {
    title: '实体与数据集 API',
    description: '只读访问规范化分类单元、化合物、证据与组学关联。',
    scope: '需要已加载语料的 PostgreSQL。',
    link: 'http://127.0.0.1:8000/docs',
    external: true,
  },
]

export function OverviewPage() {
  return (
    <>
      <header className="page-header">
        <h1>RhizoNP Navigator</h1>
        <p className="subtitle">
          面向植物–微生物与微生物天然产物研究的证据约束 AI 平台
        </p>
      </header>

      <div className="card">
        <h2>科学工作流</h2>
        <div className="flow-diagram">
          {FLOW_STEPS.map((step, i) => (
            <span key={step} style={{ display: 'contents' }}>
              <span className="flow-step">{step}</span>
              {i < FLOW_STEPS.length - 1 && <span className="flow-arrow">→</span>}
            </span>
          ))}
        </div>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', margin: 0 }}>
          各阶段保留溯源信息并应用保守证据分级。评估指标仅适用于已声明的 benchmark 范围。
        </p>
      </div>

      <div className="capability-grid">
        {CAPABILITIES.map((cap) => (
          <div key={cap.title} className="card capability-card">
            <h3>{cap.title}</h3>
            <p>{cap.description}</p>
            <p style={{ fontSize: '0.8rem', fontStyle: 'italic' }}>
              范围：{cap.scope}
            </p>
            {cap.external ? (
              <a href={cap.link} target="_blank" rel="noopener noreferrer">
                打开 API 文档 →
              </a>
            ) : (
              <Link to={cap.link}>进入 →</Link>
            )}
          </div>
        ))}
      </div>

      <div className="panel-info" style={{ marginTop: '1rem' }}>
        <strong>数据范围与科学边界</strong>
        <p style={{ margin: '0.5rem 0 0' }}>
          本平台在有界语料与保守证据策略下运行。完整说明见{' '}
          <Link to="/about/limitations">数据范围与系统边界</Link>。
        </p>
      </div>
    </>
  )
}
