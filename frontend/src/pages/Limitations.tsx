import { Link } from 'react-router-dom'

export function LimitationsPage() {
  return (
    <>
      <header className="page-header">
        <h1>数据范围与系统边界</h1>
        <p className="subtitle">
          RhizoNP Navigator 是证据约束型研究平台，以下说明当前版本的能力边界与科学限制。
        </p>
      </header>

      <section className="card">
        <h2>当前数据范围</h2>
        <ul>
          <li>文献语料为有界索引（含 bounded PubMed 快照与离线 fixture），非 PubMed 全库检索。</li>
          <li>天然产物关联优先使用 bounded NPAtlas 快照，缺失时回退至本地 fixture 记录。</li>
          <li>分类学规范化优先使用 bounded NCBI 缓存，缺失时回退至本地别名 fixture。</li>
          <li>默认稠密检索使用确定性 hashing 嵌入（可配置模型提供者）；reranker 默认为 lexical。</li>
        </ul>
      </section>

      <section className="card">
        <h2>科学边界</h2>
        <ul>
          <li>相关或共现不等于因果，不能替代实验验证。</li>
          <li>属级 16S 观测不能支持菌株级或种级天然产物生产主张。</li>
          <li>未确认 LC-MS 特征不得提升为已确认化合物身份。</li>
          <li>证据冲突时返回 <code>CONFLICTING_EVIDENCE</code>，不会强行给出单一答案。</li>
        </ul>
      </section>

      <section className="card">
        <h2>系统能力说明</h2>
        <ul>
          <li>非自主 agent，无多工具循环编排。</li>
          <li>大模型写作为可选能力；未配置 API key 或校验失败时自动回退确定性写作器。</li>
          <li>引用忠实度未经人工标注验证；仅报告结构校验与启发式诊断。</li>
          <li>自有数据流程需指定数据目录；当前不支持浏览器端文件上传。</li>
          <li>Phase 2 真实 PubMed benchmark 人工标注尚未完成，不对外宣称 PubMed 级检索准确率。</li>
        </ul>
      </section>

      <section className="card">
        <h2>评估与指标</h2>
        <p>
          合成 gold 集与 MVP 回放用例上的完美分数，<strong>不</strong>代表 PubMed 全库或生产语料上的检索质量。
          详见仓库文档 <code>docs/LIMITATIONS.md</code> 与 <code>docs/BENCHMARK_SCOPE.md</code>。
        </p>
      </section>

      <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
        <Link to="/">返回科研问答</Link>
        {' · '}
        <Link to="/overview">查看工作流概览</Link>
      </p>
    </>
  )
}
