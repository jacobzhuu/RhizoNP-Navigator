import { Link } from 'react-router-dom'
import { IconCheck, IconDocument, IconFlask, IconInfo, IconShield, IconTarget, IconX } from '../components/icons'
import { FeaturePage, PageHeader } from '../components/PageShell'

const CAPABILITIES = [
  '回答天然产物、微生物和根际互作相关科研问题。',
  '解释微生物–代谢物关联等组学发现。',
  '连接外部文献片段并保留 DOI、PMID、source 等来源信息。',
  '关联 bounded NPAtlas 与本地候选天然产物记录。',
  '识别分类学外推风险，例如属级 16S 到菌株级生产主张。',
  '给出结论边界和下一步验证建议。',
]

const LIMITATIONS = [
  '不能证明因果关系。',
  '不能替代实验验证。',
  '不能把属级 16S 直接解释为菌株级天然产物生产能力。',
  '不是 PubMed 全库检索系统。',
  'bounded corpus 之外的信息可能缺失。',
]

const METHODS = [
  '文献语料为有界索引，包含 bounded PubMed 快照与离线 fixture，非 PubMed 全库。',
  '天然产物关联优先使用 bounded NPAtlas 快照，缺失时回退到本地 fixture 记录。',
  '分类学规范化优先使用 bounded NCBI 缓存，缺失时回退到本地别名 fixture。',
  '默认稠密检索使用确定性 hashing 嵌入，可按配置切换模型提供者。',
  '大模型写作为可选能力；未配置 API key 或校验失败时回退确定性写作器。',
  '当前 benchmark 只代表声明范围内的评估结果，不代表开放世界检索准确率。',
]

export function LimitationsPage() {
  return (
    <FeaturePage>
      <PageHeader
        icon={IconInfo}
        iconTheme="blue"
        title="关于 RhizoNP Navigator"
        subtitle="面向微生物–代谢物与天然产物研究的 evidence-grounded 科研辅助工具"
      />

      <div className="about-grid">
        <section className="about-panel about-panel--position">
          <div className="about-panel-header">
            <span className="about-section-icon about-section-icon--blue">
              <IconTarget size={20} />
            </span>
            <h2>系统定位</h2>
          </div>
          <p>
            RhizoNP Navigator 将科研问题或组学发现连接到有界文献、天然产物记录、分类学边界和证据约束写作器。
            它用于形成可追溯的候选解释和验证建议，而不是替代实验判断。
          </p>
        </section>

        <section className="about-panel about-panel--can">
          <div className="about-panel-header">
            <span className="about-section-icon about-section-icon--green">
              <IconFlask size={20} />
            </span>
            <h2>能做什么</h2>
          </div>
          <ul className="about-boundary-list">
            {CAPABILITIES.map((item) => (
              <li key={item}>
                <IconCheck size={15} className="about-list-icon about-list-icon--check" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="about-panel about-panel--cannot">
          <div className="about-panel-header">
            <span className="about-section-icon about-section-icon--red">
              <IconShield size={20} />
            </span>
            <h2>不能做什么</h2>
          </div>
          <ul className="about-boundary-list">
            {LIMITATIONS.map((item) => (
              <li key={item}>
                <IconX size={15} className="about-list-icon about-list-icon--x" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="about-panel about-panel--methods">
          <div className="about-panel-header">
            <span className="about-section-icon about-section-icon--slate">
              <IconDocument size={20} />
            </span>
            <h2>数据与方法</h2>
          </div>
          <ul className="about-methods-list">
            {METHODS.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <p className="muted-text feature-page-footer-links">
        <Link to="/">返回首页</Link>
        {' · '}
        <Link to="/ask">科研问答</Link>
        {' · '}
        <Link to="/results">结果解释</Link>
      </p>
    </FeaturePage>
  )
}
