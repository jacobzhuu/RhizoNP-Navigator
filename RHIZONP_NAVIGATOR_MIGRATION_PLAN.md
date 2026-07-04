# RhizoNP Navigator 详细迁移方案

> **项目全称**：RhizoNP Navigator：面向植物—微生物互作与微生物天然产物的证据增强检索系统
> **英文名称**：RhizoNP Navigator: An Evidence-Grounded Retrieval and Candidate Linking System for Plant–Microbe Interactions and Microbial Natural Products
> **文档类型**：工程迁移设计 + 科研定位方案 + Codex 实施蓝图
> **版本**：v1.0
> **日期**：2026-07-05
> **适用仓库基线**：`jacobzhuu/RAGNavigator` 当前公开版本
> **建议文件位置**：仓库根目录 `docs/RHIZONP_NAVIGATOR_MIGRATION_PLAN.md` 或根目录直接保存本文件

---

## 0. 执行摘要

本项目不应被简单改造成“天然产物 RAG 问答机器人”，也不应直接跳跃到蛋白语言模型、BGC 预测或抗菌肽生成。最优迁移路线是：

```text
现有 RAGNavigator
    │
    │  语义召回 + Reranker + UUID + PostgreSQL + LLM
    ▼
科研证据检索底座
    │
    │  文献实体化 + 来源追踪 + 结构化证据
    ▼
Plant–Microbe Evidence Navigator
    │
    │  Taxon / Metabolite / Host / Phenotype
    ▼
RhizoNP Navigator
    │
    │  微生物—天然产物—生物活性连接
    ▼
Own-data-to-literature
    │
    │  16S / LC-MS / sPLS / 网络结果 → 外部证据
    ▼
未来扩展
    ├── SMILES / 分子表示
    ├── Protein embedding
    ├── BGC / MIBiG
    └── Agent workflow
```

迁移后的项目核心定位：

> **将用户自己的植物—微生物多组学观察，与外部微生物天然产物文献和结构化数据库连接，并通过分类学层级、证据来源、实体一致性和实验验证状态对候选关系进行约束，输出可追溯、可拒答、可验证的科研假设，而不是生成无边界的自然语言答案。**

项目的三个核心差异化能力：

1. **Taxonomy-aware**：明确区分 strain / species / genus 等证据层级，禁止将 16S 属水平观察直接外推为具体菌株产物。
2. **Evidence-aware**：每个结论必须绑定来源、证据类型、直接性与置信等级；无证据时返回 `INSUFFICIENT_EVIDENCE`。
3. **Own-data-to-literature**：允许导入用户自己的 16S、LC-MS、相关网络、sPLS 或差异分析结果，将内部观察与外部文献/天然产物证据连接。

本方案优先追求：

- 科研问题真实；
- 与申请者现有根际代谢组和微生物组研究自然衔接；
- 与微生物天然产物、植物—微生物互作、AI 多组学、科研智能体方向形成可解释迁移；
- 代码可复现、可测试、可评估；
- 避免“为了申请导师临时换皮”的观感。

---

# 1. 迁移背景与学术定位

## 1.1 申请者现有科研主线

现有研究基础可抽象为：

```text
植物胁迫 / 机械根损伤 / 资源限制
              │
              ▼
      根际代谢组重编程
              │
              ├──────────────┐
              ▼              ▼
      LC-MS features      16S taxa
              │              │
              └──────┬───────┘
                     ▼
       多组学关联 / sPLS / 网络
                     │
                     ▼
     候选代谢物—候选微生物关系
                     │
                     ▼
        生物学解释与实验假设
```

这一主线已经具备：

- 植物—微生物互作问题意识；
- 非靶向 LC-MS 高维数据经验；
- 16S 群落分析经验；
- 多组学关联经验；
- 候选代谢物、候选菌群和网络枢纽识别经验；
- R/Python 数据分析能力。

缺口不是“没有生物学问题”，而是：

> **内部多组学观察如何系统连接外部机制证据、微生物天然产物知识与可验证候选假设？**

RhizoNP Navigator 应直接解决这一缺口。

---

## 1.2 目标导师方向中的真实连接点

依据课题组官网当前公开信息，研究核心包括：

- microbial secondary metabolites / natural products；
- natural product discovery、regulation、biosynthesis、engineering；
- AI 与 large models；
- plant–microbe interactions；
- Type II polyketide prediction；
- AI for antimicrobial peptide modification；
- deep learning-based multi-omics joint analysis in plant–microbe interactions。

公开成果列表还包括：

- ChatT2：天然产物领域 LLM-based agent；
- MultiT2：细菌芳香聚酮天然产物多模态数据连接工具；
- MAAPE：protein embeddings 进化分析；
- DeepAden：NRPS 底物特异性可解释机器学习；
- explainable few-shot learning for antimicrobial peptides；
- ginseng rhizosphere metagenomics；
- rhizosphere-derived *Streptomyces* biocontrol。

因此项目不需要生硬地“从生态学跳到药物发现”，而应沿以下逻辑迁移：

```text
根际微生物组
    ↓
候选功能菌
    ↓
微生物代谢能力
    ↓
微生物次生代谢物 / 天然产物
    ↓
生物活性 / 生防潜力 / 植物互作
    ↓
证据增强 AI 系统
```

---

# 2. 项目使命、边界与非目标

## 2.1 项目使命

RhizoNP Navigator 的核心任务：

> **整合内部多组学结果、植物—微生物互作文献、微生物天然产物记录与结构化实体信息，建立“内部观察 → 外部证据 → 候选关系 → 证据等级 → 实验建议”的可追溯链路。**

---

## 2.2 第一阶段必须支持的科研问题

### Use Case A：Taxon → Natural Product

输入：

```text
Taxon: Streptomyces
Context: Populus rhizosphere
Phenotype: severe root injury
```

系统回答：

- 该 taxon 是否存在已报道天然产物生产记录？
- 证据是同菌株、同物种还是仅同属？
- 对应天然产物有哪些？
- 报道了什么生物活性？
- 来源论文是什么？
- 是否与植物互作/生防有关？
- 当前证据能否支持“本样本生产该化合物”？

---

### Use Case B：Metabolite → Producer / Natural Product Context

输入：

```text
Metabolite: chlorogenic acid
Context: rhizosphere stress response
```

系统回答：

- 该化合物或同义词在文献中的功能背景；
- 是否为微生物天然产物；
- 是否存在已知微生物生产来源；
- 结构确认层级；
- 与当前 LC-MS feature 的连接是否仅为名称映射、候选注释或确证。

---

### Use Case C：Own Omics Edge → External Evidence

输入 CSV：

```csv
taxon,metabolite,effect_size,padj,method,treatment,timepoint
Streptomyces,Feature_M123,0.72,0.003,sPLS,RootInjury75,Day10
Bacillus,Feature_M456,-0.61,0.008,Spearman,RootInjury100,Day45
```

系统输出：

```text
内部证据
  ↓
实体标准化
  ↓
文献检索
  ↓
天然产物记录
  ↓
分类学一致性检查
  ↓
候选关系表
  ↓
实验验证建议
```

---

### Use Case D：Evidence-bounded Question Answering

问题：

> “检测到 Streptomyces 是否说明样本中存在 formicamycin？”

正确系统行为：

```text
结论：不能直接支持。

原因：
1. 16S 属水平检测不能确认具体物种或菌株；
2. 天然产物生产具有菌株和 BGC 特异性；
3. 缺乏目标化合物 LC-MS/MS 或分离培养证据。

Evidence status: INSUFFICIENT_EVIDENCE
```

---

## 2.3 明确非目标

第一版 **不做**：

- 通用 ChatGPT 式天然产物百科；
- de novo 分子生成；
- 抗菌肽序列生成；
- BGC 端到端预测；
- 蛋白结构预测；
- 自动湿实验结论；
- 由相关性直接推断因果；
- 由属水平 16S 直接推断菌株天然产物；
- 未经验证将 LC-MS feature 宣称为结构确证化合物；
- 一开始就做复杂 autonomous agent。

这些功能会导致范围失控，并削弱项目与申请者真实研究积累的连续性。

---

# 3. 当前 RAGNavigator 基线审计与迁移原则

## 3.1 当前可复用能力

现有仓库已经具备以下真实能力：

```text
CSVLoader
  ↓
RecursiveCharacterTextSplitter
  ↓
Embedding
  ↓
FAISS
  ↓
Top-K similarity search
  ↓
Reranker
  ↓
UUID extraction
  ↓
PostgreSQL query
  ↓
LLM filtering / ranking
```

建议保留的思想：

1. **向量召回不是最终答案**；
2. **召回结果可以作为结构化实体入口**；
3. **通过稳定 ID 回查 PostgreSQL**；
4. **LLM 放在后端证据组织层，而不是事实数据库替代品**。

这正是迁移的技术基础。

---

## 3.2 当前必须先修复的问题

### P0-1：密钥泄漏

当前公开仓库历史中存在 API-key-looking credential 和数据库密码。

必须：

- 立即 rotate / revoke；
- 新建 `.env.example`；
- 所有 secrets 使用环境变量；
- `.gitignore` 增加 `.env*`；
- 使用 GitHub secret scanning；
- 需要时用 `git filter-repo` 清理历史；
- README 明确配置方式。

**验收：**

```bash
git grep -nE 'sk-|password\s*=|api_key\s*='
```

不得出现真实凭证。

---

### P0-2：Reranker wrapper 修正

当前配置模型是：

```text
BAAI/bge-reranker-v2-m3
```

但实现使用 `FlagLLMReranker`。应根据 FlagEmbedding 官方用法改为适配 `bge-reranker-v2-m3` 的 `FlagReranker`。

必须新增：

```python
class RerankerProtocol(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]:
        ...
```

避免业务代码绑定具体类。

---

### P0-3：删除逻辑修复

现有删除逻辑仅找到第一个 source 匹配 chunk 后 `break`，可能只删除单个 chunk。

应改为：

```python
matching_ids = [
    doc_id
    for doc_id, doc in vector_db.docstore._dict.items()
    if canonical_source(doc.metadata["source"]) == canonical_source(file_path)
]

vector_db.delete(matching_ids)
```

并新增测试：

- 单文件 1 chunk；
- 单文件 N chunks；
- 不存在 source；
- 同名不同路径；
- 删除后 index/docstore 一致。

---

### P0-4：路径与 Linux 兼容

移除：

```text
C:\Users\...
D:\Code\...
```

统一：

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
```

模型路径和数据库路径使用配置。

---

### P0-5：文件命名统一

当前 README 与文件真实大小写存在差异风险。

统一 PEP 8：

```text
src/rhizonp/
    config.py
    embedding.py
    reranking.py
    vector_store.py
```

---

### P0-6：依赖瘦身

不要保留整个环境 `pip freeze`。

建立：

```text
pyproject.toml
requirements.lock   # 可选
```

核心依赖只保留实际使用包。

---

### P0-7：贡献边界透明

当前 README 已说明项目基于他人工作进行改造。

迁移后必须新增：

```text
docs/PROVENANCE.md
```

说明：

- 原始基线；
- 当前作者新增模块；
- 重构范围；
- 迁移后的原创设计；
- upstream credit。

对申博而言，“透明改造并做出明确新增贡献”优于模糊宣称“独立开发”。

---

# 4. 目标系统架构

## 4.1 总体架构

```text
┌─────────────────────────────────────────────┐
│                User Interface               │
│ Query / Upload Omics Edge / Evidence Review │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│             Scientific Query Parser         │
│ taxon | metabolite | compound | host        │
│ phenotype | treatment | timepoint | intent  │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│              Entity Normalization           │
│ Taxonomy | Compound Synonym | DOI | IDs      │
└────────────┬───────────────────┬─────────────┘
             │                   │
             ▼                   ▼
┌──────────────────┐   ┌──────────────────────┐
│ Structured Query │   │ Retrieval Pipeline   │
│ PostgreSQL       │   │ BM25 / Dense / Hybrid│
└────────┬─────────┘   └──────────┬───────────┘
         │                        ▼
         │              ┌──────────────────────┐
         │              │ Candidate Reranking  │
         │              │ Reranker + Metadata  │
         │              └──────────┬───────────┘
         └──────────────┬──────────┘
                        ▼
┌─────────────────────────────────────────────┐
│           Evidence Linking Engine           │
│ claim ↔ source ↔ entity ↔ evidence tier     │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│        Scientific Constraint Validator      │
│ taxonomy / structure / causality / provenance│
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│         Evidence-Grounded LLM Writer        │
│ answer + citations + uncertainty + refusal  │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│         Candidate Hypothesis Report         │
│ evidence matrix | ranking | experiment next │
└─────────────────────────────────────────────┘
```

---

## 4.2 关键设计原则

### 原则 A：LLM 不拥有事实

事实来源：

- PostgreSQL；
- 文献；
- 数据库记录；
- 用户自己的组学结果。

LLM 只负责：

- query understanding；
- constrained synthesis；
- evidence-aware explanation。

---

### 原则 B：所有关键结论必须有 Evidence Object

禁止：

```python
answer = llm.invoke(question)
```

应为：

```python
evidence_bundle = retrieval_service.retrieve(question)
validated_bundle = evidence_validator.validate(evidence_bundle)
answer = grounded_writer.generate(question, validated_bundle)
```

---

### 原则 C：未知必须可表示

系统状态至少包括：

```python
SUPPORTED
PARTIALLY_SUPPORTED
CONFLICTING_EVIDENCE
INSUFFICIENT_EVIDENCE
UNRESOLVED_ENTITY
```

不得把“没有找到”自动转成“否”。

---

# 5. 推荐仓库目录结构

```text
RhizoNP-Navigator/
├── README.md
├── LICENSE
├── pyproject.toml
├── .env.example
├── .gitignore
├── Makefile
├── docker-compose.yml
│
├── docs/
│   ├── RHIZONP_NAVIGATOR_MIGRATION_PLAN.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── EVIDENCE_POLICY.md
│   ├── EVALUATION.md
│   ├── PROVENANCE.md
│   └── SECURITY.md
│
├── config/
│   ├── default.yaml
│   ├── dev.yaml
│   └── eval.yaml
│
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   ├── fixtures/
│   └── eval/
│
├── migrations/
│   └── versions/
│
├── src/
│   └── rhizonp/
│       ├── __init__.py
│       ├── cli.py
│       ├── settings.py
│       │
│       ├── domain/
│       │   ├── models.py
│       │   ├── enums.py
│       │   ├── evidence.py
│       │   └── policies.py
│       │
│       ├── ingestion/
│       │   ├── base.py
│       │   ├── literature.py
│       │   ├── own_omics.py
│       │   ├── npatlas.py
│       │   ├── taxonomy.py
│       │   └── mibig.py
│       │
│       ├── normalization/
│       │   ├── taxonomy.py
│       │   ├── compounds.py
│       │   ├── literature_ids.py
│       │   └── synonyms.py
│       │
│       ├── retrieval/
│       │   ├── dense.py
│       │   ├── lexical.py
│       │   ├── hybrid.py
│       │   ├── reranker.py
│       │   ├── filters.py
│       │   └── types.py
│       │
│       ├── evidence/
│       │   ├── linker.py
│       │   ├── grader.py
│       │   ├── validator.py
│       │   ├── conflict.py
│       │   └── bundle.py
│       │
│       ├── query/
│       │   ├── parser.py
│       │   ├── planner.py
│       │   └── expansion.py
│       │
│       ├── llm/
│       │   ├── client.py
│       │   ├── prompts.py
│       │   ├── writer.py
│       │   └── schemas.py
│       │
│       ├── services/
│       │   ├── search_service.py
│       │   ├── evidence_service.py
│       │   ├── own_data_service.py
│       │   └── report_service.py
│       │
│       ├── storage/
│       │   ├── postgres.py
│       │   ├── repositories.py
│       │   ├── vector_store.py
│       │   └── bm25_store.py
│       │
│       ├── api/
│       │   ├── app.py
│       │   ├── routes_search.py
│       │   ├── routes_evidence.py
│       │   └── routes_upload.py
│       │
│       └── evaluation/
│           ├── retrieval.py
│           ├── grounding.py
│           ├── abstention.py
│           └── reports.py
│
├── scripts/
│   ├── bootstrap_db.py
│   ├── ingest_literature.py
│   ├── ingest_own_omics.py
│   ├── build_indexes.py
│   ├── run_eval.py
│   └── export_demo_report.py
│
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── fixtures/
```

---

# 6. 领域对象设计

## 6.1 核心实体

### Paper

```python
class Paper:
    paper_id: UUID
    doi: str | None
    pmid: str | None
    pmcid: str | None
    title: str
    abstract: str | None
    year: int | None
    journal: str | None
    source_url: str | None
    license: str | None
    provenance: dict
```

---

### Taxon

```python
class Taxon:
    taxon_id: UUID
    canonical_name: str
    rank: str
    strain: str | None
    species: str | None
    genus: str | None
    family: str | None
    external_ids: dict
    normalization_status: str
```

---

### Compound

```python
class Compound:
    compound_id: UUID
    canonical_name: str
    synonyms: list[str]
    smiles: str | None
    inchikey: str | None
    formula: str | None
    compound_class: str | None
    structure_status: str
```

---

### NaturalProductRecord

```python
class NaturalProductRecord:
    np_record_id: UUID
    compound_id: UUID
    producer_taxon_id: UUID | None
    source_database: str
    external_record_id: str
    evidence_reference_id: UUID | None
    bioactivity_summary: str | None
    provenance: dict
```

---

### OmicsObservation

```python
class OmicsObservation:
    observation_id: UUID
    dataset_id: UUID
    entity_type: str
    entity_id: UUID | None
    raw_label: str
    treatment: str | None
    timepoint: str | None
    layer: str | None
    effect_size: float | None
    p_value: float | None
    adjusted_p: float | None
    method: str
```

---

### OmicsAssociation

```python
class OmicsAssociation:
    association_id: UUID
    dataset_id: UUID
    source_entity_id: UUID | None
    target_entity_id: UUID | None
    source_raw_label: str
    target_raw_label: str
    score: float
    adjusted_p: float | None
    method: str
    direction: str | None
    metadata: dict
```

---

### Evidence

```python
class Evidence:
    evidence_id: UUID
    claim_type: str
    subject_entity_id: UUID
    predicate: str
    object_entity_id: UUID | None
    object_literal: str | None
    source_type: str
    source_id: UUID
    evidence_level: str
    directness: str
    extraction_method: str
    confidence: float
    supporting_span: str | None
    provenance: dict
```

---

### CandidateLink

```python
class CandidateLink:
    candidate_id: UUID
    source_entity_id: UUID
    relation: str
    target_entity_id: UUID
    internal_evidence_score: float | None
    external_evidence_score: float | None
    taxonomy_distance: str | None
    evidence_tier: str
    status: str
```

---

# 7. PostgreSQL 数据库 Schema

建议使用 PostgreSQL + SQLAlchemy 2 + Alembic。

## 7.1 表清单

```text
papers
paper_chunks
taxa
taxon_synonyms
compounds
compound_synonyms
natural_product_records
bioactivities
datasets
omics_observations
omics_associations
evidence_items
candidate_links
retrieval_runs
retrieval_results
answer_runs
answer_citations
ingestion_runs
```

---

## 7.2 最小 SQL DDL 示例

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE papers (
    paper_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doi TEXT UNIQUE,
    pmid TEXT,
    pmcid TEXT,
    title TEXT NOT NULL,
    abstract TEXT,
    year INTEGER,
    journal TEXT,
    source_url TEXT,
    license TEXT,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE taxa (
    taxon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    rank TEXT,
    strain TEXT,
    species TEXT,
    genus TEXT,
    family TEXT,
    external_ids JSONB NOT NULL DEFAULT '{}'::jsonb,
    normalization_status TEXT NOT NULL DEFAULT 'unresolved',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_taxa_canonical_name
ON taxa (lower(canonical_name));

CREATE TABLE compounds (
    compound_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    smiles TEXT,
    inchikey TEXT,
    formula TEXT,
    compound_class TEXT,
    structure_status TEXT NOT NULL DEFAULT 'unknown',
    external_ids JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE natural_product_records (
    np_record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    compound_id UUID NOT NULL REFERENCES compounds(compound_id),
    producer_taxon_id UUID REFERENCES taxa(taxon_id),
    source_database TEXT NOT NULL,
    external_record_id TEXT NOT NULL,
    bioactivity_summary TEXT,
    reference_paper_id UUID REFERENCES papers(paper_id),
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_database, external_record_id)
);

CREATE TABLE datasets (
    dataset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    owner TEXT,
    data_type TEXT NOT NULL,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE omics_associations (
    association_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES datasets(dataset_id),
    source_entity_type TEXT NOT NULL,
    source_entity_id UUID,
    source_raw_label TEXT NOT NULL,
    target_entity_type TEXT NOT NULL,
    target_entity_id UUID,
    target_raw_label TEXT NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    adjusted_p DOUBLE PRECISION,
    method TEXT NOT NULL,
    direction TEXT,
    treatment TEXT,
    timepoint TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE evidence_items (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_type TEXT NOT NULL,
    subject_entity_type TEXT NOT NULL,
    subject_entity_id UUID NOT NULL,
    predicate TEXT NOT NULL,
    object_entity_type TEXT,
    object_entity_id UUID,
    object_literal TEXT,
    source_type TEXT NOT NULL,
    source_id UUID NOT NULL,
    evidence_tier TEXT NOT NULL,
    directness TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    supporting_span TEXT,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE candidate_links (
    candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_type TEXT NOT NULL,
    source_entity_id UUID NOT NULL,
    relation TEXT NOT NULL,
    target_entity_type TEXT NOT NULL,
    target_entity_id UUID NOT NULL,
    internal_evidence_score DOUBLE PRECISION,
    external_evidence_score DOUBLE PRECISION,
    taxonomy_distance TEXT,
    evidence_tier TEXT NOT NULL,
    status TEXT NOT NULL,
    rationale JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

# 8. Evidence Policy：项目最关键的科研约束

单独建立：

```text
docs/EVIDENCE_POLICY.md
```

---

## 8.1 Taxonomy Evidence Tier

### Tier A：Same strain

条件：

```text
内部/查询对象的 strain
==
外部天然产物记录 producer strain
```

允许表达：

> “存在直接菌株级生产证据。”

---

### Tier B：Same species, different/unknown strain

允许表达：

> “同物种已有生产记录，但当前样本菌株是否具备该能力仍需验证。”

---

### Tier C：Same genus

允许表达：

> “同属成员存在相关记录，仅构成候选线索。”

禁止：

> “该样本产生此天然产物。”

---

### Tier D：Higher taxonomic or semantic similarity only

只允许作为检索线索，不应进入强结论。

---

## 8.2 Chemical Identification Tier

### C1：Confirmed structure

例如：

- 标准品比对；
- 充分 MS/MS；
- NMR；
- 数据库确证记录。

### C2：Putatively annotated

例如：

- 高质量 MS/MS 库匹配；
- 合理候选注释。

### C3：Formula/class-level

只能支持分子式或化合物类别。

### C4：Unknown feature

例如：

```text
M123
m/z 353.087
RT 5.42
```

禁止自动转成具体化合物。

---

## 8.3 Causality Policy

系统必须内置：

```text
correlation != causation
co-occurrence != biochemical interaction
taxonomic presence != metabolite production
same genus != same biosynthetic capacity
LLM retrieval match != experimental evidence
```

---

## 8.4 Refusal Policy

以下情况输出：

```text
INSUFFICIENT_EVIDENCE
```

- 未找到可靠来源；
- 实体无法标准化；
- 仅属水平信息却要求菌株结论；
- LC-MS feature 未确证却要求具体结构；
- 只有相关性却要求因果机制；
- 来源互相冲突且无法判断；
- 结论超出当前 evidence bundle。

---

# 9. 数据源迁移策略

## 9.1 数据源分层

### Layer 1：申请者自己的研究数据

优先级最高。

可导入：

- Rhizosphere 项目候选菌；
- 候选代谢物；
- sPLS loading；
- Procrustes 辅助结果；
- Spearman/SparCC/其他关联边；
- 网络 hub；
- treatment；
- timepoint；
- soil layer；
- effect size；
- adjusted p-value。

**第一版允许使用脱敏、裁剪或示例数据。**

---

### Layer 2：植物—微生物互作文献

推荐数据入口：

- PubMed / NCBI E-utilities；
- Crossref metadata；
- 合法开放获取全文；
- 用户自行提供 PDF。

必须尊重：

- 版权；
- API rate limit；
- full-text 许可；
- 数据再分发条款。

---

### Layer 3：微生物天然产物数据

优先考虑：

- Natural Products Atlas；
- 可合法下载/使用的开放天然产物数据；
- 公开文献元数据。

Natural Products Atlas 当前官网说明其开放覆盖 bacterial and fungal natural products，并支持 compound、origin、bioactivity 等探索；当前条款/许可必须在实施时再次核对。

---

### Layer 4：BGC 数据（后续）

可选：

- MIBiG。

第一版只做 adapter interface，不强制接入。

原因：

- BGC 会显著扩大生物信息学范围；
- 容易让第一版失焦；
- 应在 Taxon–Natural Product 证据链稳定后再加入。

---

## 9.2 Adapter 设计

```python
class SourceAdapter(Protocol):
    source_name: str

    def fetch(self, query: dict) -> list[RawRecord]:
        ...

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        ...

    def provenance(self, record: RawRecord) -> dict:
        ...
```

具体：

```python
class PubMedAdapter(SourceAdapter): ...
class CrossrefAdapter(SourceAdapter): ...
class NPAtlasAdapter(SourceAdapter): ...
class OwnOmicsAdapter(SourceAdapter): ...
class MibigAdapter(SourceAdapter): ...
```

---

# 10. Own-data-to-literature 模块设计

这是本项目最重要的差异化模块。

## 10.1 输入格式

### Associations CSV

```csv
source_type,source_label,target_type,target_label,score,padj,method,treatment,timepoint
taxon,Streptomyces,metabolite,Feature_M123,0.72,0.003,sPLS,RI75,D10
taxon,Bacillus,metabolite,chlorogenic acid,-0.61,0.008,Spearman,RI100,D45
```

---

### Taxa CSV

```csv
feature_id,taxon_name,rank,relative_abundance,treatment,timepoint
ASV_001,Streptomyces,genus,0.031,RI75,D10
```

---

### Metabolites CSV

```csv
feature_id,name,mz,rt,annotation_level,inchikey,smiles
M123,,353.087,5.42,C4,,
M456,chlorogenic acid,353.087,5.42,C2,,
```

---

## 10.2 导入流程

```text
CSV
 ↓
Schema validation
 ↓
Raw label preservation
 ↓
Entity normalization
 ↓
Resolution status
 ↓
PostgreSQL
 ↓
Candidate evidence search
```

---

## 10.3 实体解析状态

```text
RESOLVED_EXACT
RESOLVED_SYNONYM
RESOLVED_AMBIGUOUS
UNRESOLVED
```

任何 `UNRESOLVED` 实体不得被强行连接。

---

## 10.4 输出 Candidate Matrix

```text
| Internal taxon | Internal metabolite | Internal score |
| External NP candidate | Taxonomy distance |
| External paper count | Best evidence tier |
| Conflict flag | Proposed validation |
```

示例：

```text
Streptomyces
  ↕ sPLS 0.72
Feature_M123
  ↓
External evidence:
- NP candidate X
- same genus only
- 3 papers
- no same-strain evidence

Status:
PARTIALLY_SUPPORTED

Suggested validation:
targeted LC-MS/MS + isolate-level sequencing
```

---

# 11. 检索架构

## 11.1 第一阶段：Dense Retrieval

保留 FAISS，但封装接口。

```python
class DenseRetriever:
    def search(
        self,
        query: str,
        *,
        k: int,
        filters: dict | None = None
    ) -> list[RetrievedChunk]:
        ...
```

---

## 11.2 第二阶段：Lexical Retrieval

增加 BM25。

原因：

生物学实体名称中：

- gene symbols；
- strain IDs；
- compound names；
- BGC IDs；
- DOI；
- accession。

纯 dense retrieval 可能不稳定。

---

## 11.3 第三阶段：Hybrid Retrieval

推荐：

```text
dense_rank
lexical_rank
metadata_match
        ↓
Reciprocal Rank Fusion
        ↓
candidate pool
```

示例：

```python
score = (
    w_dense * dense_score
    + w_lexical * lexical_score
    + w_metadata * metadata_score
)
```

第一版不必追求复杂学习排序。

---

## 11.4 第四阶段：Reranker

修正当前 wrapper。

接口：

```python
class Reranker:
    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int
    ) -> list[RetrievedChunk]:
        ...
```

支持：

```text
NoReranker
BGEReranker
FutureCrossEncoder
```

---

## 11.5 Metadata Filter

文献 chunk metadata：

```json
{
  "paper_id": "...",
  "doi": "...",
  "year": 2025,
  "section": "results",
  "taxa": ["Streptomyces"],
  "compounds": ["..."],
  "host": ["Panax ginseng"],
  "source_type": "paper"
}
```

支持：

```text
year >= 2020
source_type = paper
taxon = Streptomyces
section in [results, discussion]
```

---

# 12. 文献 Chunking 策略

不要继续简单固定字符切块。

## 12.1 优先结构化切分

```text
Title
Abstract
Introduction
Methods
Results
Discussion
Figure captions
Tables
```

---

## 12.2 Chunk metadata

每个 chunk：

```python
{
    "chunk_id": "...",
    "paper_id": "...",
    "section": "results",
    "paragraph_index": 12,
    "char_start": 1024,
    "char_end": 1842,
    "doi": "...",
    "source_hash": "...",
}
```

---

## 12.3 不同 section 权重

用于候选证据排序：

```text
Results       > Discussion
Abstract      > Introduction
Methods       contextual
```

但不得简单将 Discussion 视为事实。

---

# 13. Entity Normalization

## 13.1 Taxonomy normalization

输入：

```text
Streptomyces sp.
S. hygroscopicus
Streptomyces hygroscopicus OS-2
```

输出：

```python
NormalizedTaxon(
    canonical_name=...,
    rank=...,
    species=...,
    strain=...,
    external_ids=...,
    confidence=...
)
```

---

## 13.2 Taxonomy distance

实现：

```python
def taxonomy_distance(a: Taxon, b: Taxon) -> str:
    if same_strain(a, b):
        return "same_strain"
    if same_species(a, b):
        return "same_species"
    if same_genus(a, b):
        return "same_genus"
    if same_family(a, b):
        return "same_family"
    return "distant"
```

这是 evidence tier 的基础。

---

## 13.3 Compound normalization

处理：

- canonical name；
- synonyms；
- InChIKey；
- SMILES；
- formula。

第一版：

> 名称 + synonym + external IDs

第二版：

> 结构检索。

---

# 14. Evidence Linking Engine

## 14.1 输入

```python
LinkRequest(
    source_entity=taxon,
    relation="PRODUCES",
    target_entity=compound
)
```

---

## 14.2 检索

```text
Structured records
  +
Literature evidence
  +
Own omics evidence
```

---

## 14.3 Evidence score

建议不是单一神秘分数，而是可解释分项：

```python
EvidenceScore(
    taxonomy=0.0,
    source_quality=0.0,
    directness=0.0,
    replication=0.0,
    recency=0.0,
    internal_support=0.0
)
```

---

## 14.4 示例规则

```python
if taxonomy_distance == "same_strain":
    taxonomy_score = 1.0
elif taxonomy_distance == "same_species":
    taxonomy_score = 0.75
elif taxonomy_distance == "same_genus":
    taxonomy_score = 0.40
else:
    taxonomy_score = 0.10
```

**注意：这些权重仅是工程初值，必须在文档中声明为 heuristic，不得冒充统计概率。**

---

## 14.5 冲突处理

例如：

- Paper A 支持关系；
- Paper B 否定；
- 数据库无记录。

输出：

```text
CONFLICTING_EVIDENCE
```

而不是由 LLM 随机选一边。

---

# 15. LLM 层设计

## 15.1 LLM 角色

只承担：

- query parsing；
- constrained query expansion；
- evidence synthesis；
- report wording。

不承担：

- taxonomy truth；
- database truth；
- chemical identity confirmation。

---

## 15.2 强制结构化输出

使用 Pydantic schema。

```python
class GroundedAnswer(BaseModel):
    status: Literal[
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "CONFLICTING_EVIDENCE",
        "INSUFFICIENT_EVIDENCE",
        "UNRESOLVED_ENTITY",
    ]
    answer: str
    claims: list["Claim"]
    limitations: list[str]
    suggested_validations: list[str]
```

```python
class Claim(BaseModel):
    text: str
    evidence_ids: list[str]
    confidence_label: Literal["high", "medium", "low"]
```

---

## 15.3 Prompt 约束

System prompt 必须明确：

```text
1. 只能使用 provided evidence。
2. 每个事实性 claim 必须引用 evidence_id。
3. 不得把 same-genus evidence 表述成 same-strain evidence。
4. 不得把 16S presence 表述成 metabolite production。
5. 不得把 correlation 表述成 causality。
6. 若 evidence 不足，status=INSUFFICIENT_EVIDENCE。
```

---

# 16. API 设计

建议 FastAPI。

## 16.1 搜索

```http
POST /api/v1/search
```

```json
{
  "query": "Streptomyces natural products associated with plant biocontrol",
  "filters": {
    "year_from": 2020
  },
  "top_k": 10
}
```

---

## 16.2 Evidence query

```http
POST /api/v1/evidence/query
```

```json
{
  "subject": {
    "type": "taxon",
    "name": "Streptomyces"
  },
  "relation": "PRODUCES",
  "object": {
    "type": "compound",
    "name": "formicamycin"
  }
}
```

---

## 16.3 Own omics upload

```http
POST /api/v1/omics/associations
```

文件：

```text
multipart/form-data
```

---

## 16.4 Candidate linking

```http
POST /api/v1/candidates/link
```

---

## 16.5 Grounded answer

```http
POST /api/v1/answer
```

必须返回：

```json
{
  "status": "PARTIALLY_SUPPORTED",
  "answer": "...",
  "claims": [...],
  "evidence": [...],
  "limitations": [...],
  "suggested_validations": [...]
}
```

---

# 17. 评测体系

没有评测，项目仍只是 Demo。

## 17.1 构建最小 Benchmark

目标：

```text
100 questions
```

分组：

| 类别 | 数量 |
|---|---:|
| Plant–microbe | 20 |
| Taxon–natural product | 20 |
| Compound–bioactivity | 20 |
| Own-data-to-literature | 20 |
| Must-abstain / trick questions | 20 |

---

## 17.2 Retrieval Gold Set

每个 query：

```json
{
  "query_id": "Q001",
  "query": "...",
  "relevant_chunk_ids": ["C11", "C82"],
  "relevant_paper_ids": ["P5"],
  "must_abstain": false
}
```

---

## 17.3 Retrieval metrics

必须实现：

```text
Recall@5
Recall@10
MRR@10
nDCG@10
```

---

## 17.4 Ablation

至少：

```text
A. BM25 only
B. Dense only
C. Dense + Reranker
D. Hybrid
E. Hybrid + Reranker
F. Hybrid + Reranker + Metadata Filter
G. + Structured DB linking
```

输出：

```text
reports/eval/retrieval_ablation.csv
reports/eval/retrieval_ablation.md
```

---

## 17.5 Grounding metrics

### Citation Precision

claim 的 citation 是否真正支持该 claim。

### Citation Coverage

事实 claim 是否都有 citation。

### Faithfulness

回答是否超出 evidence bundle。

### Abstention Accuracy

应拒答时是否拒答。

### Taxonomy Safety Accuracy

是否错误越过 taxonomy evidence tier。

---

# 18. 测试计划

## 18.1 Unit tests

必须覆盖：

- chunk deletion；
- taxonomy distance；
- evidence tier；
- entity normalization；
- query parser；
- score fusion；
- reranker adapter；
- refusal policy；
- secret-free settings。

---

## 18.2 Integration tests

```text
CSV ingest
→ PostgreSQL
→ index
→ search
→ rerank
→ evidence bundle
→ grounded answer
```

---

## 18.3 Contract tests

对外部 adapter：

- API timeout；
- empty response；
- malformed record；
- rate limit；
- schema change。

---

## 18.4 Scientific policy tests

示例：

```python
def test_genus_level_evidence_cannot_claim_strain_production():
    ...
```

```python
def test_unknown_lcms_feature_cannot_be_named_as_confirmed_compound():
    ...
```

```python
def test_correlation_cannot_be_rendered_as_causality():
    ...
```

这类测试是项目最重要的“科研安全单元测试”。

---

# 19. 可复现性与工程规范

## 19.1 配置

使用：

```python
pydantic-settings
```

`.env.example`：

```env
DATABASE_URL=postgresql+psycopg://rhizonp:rhizonp@localhost:5432/rhizonp
LLM_PROVIDER=openai_compatible
LLM_MODEL=
LLM_API_KEY=
EMBEDDING_MODEL=
RERANKER_MODEL=
```

---

## 19.2 Docker

`docker-compose.yml` 至少：

```text
postgres
app
```

FAISS 可保留本地 volume。

---

## 19.3 Makefile

```makefile
setup
lint
test
db-up
db-migrate
ingest-demo
build-index
eval
run
```

---

## 19.4 CI

GitHub Actions：

```text
ruff
mypy
pytest
secret scan
```

---

# 20. 前端与 Demo 建议

第一版不需要复杂前端。

推荐 Streamlit 或轻量 React/FastAPI。

必须展示四个页面：

## Page 1：Evidence Search

```text
Query
Filters
Retrieved passages
Rerank scores
Source metadata
```

---

## Page 2：Taxon–NP Candidate Link

```text
Taxon
Natural Product
Taxonomy distance
Evidence tier
Papers
Bioactivity
Limitations
```

---

## Page 3：Own-data-to-literature

上传：

```text
associations.csv
```

展示：

```text
Internal edge
External evidence
Candidate rank
Validation suggestion
```

---

## Page 4：Audit View

展示：

```text
claim
→ evidence_id
→ source
→ supporting span
→ tier
→ confidence
```

这个页面对申博展示非常重要。

---

# 21. 迁移里程碑

---

## Phase 0：安全与基线修复

### 目标

让原项目成为可维护基线。

### 任务

- [ ] rotate secrets
- [ ] `.env.example`
- [ ] 清理硬编码密码
- [ ] 修正 reranker wrapper
- [ ] 修复多 chunk 删除
- [ ] 路径跨平台
- [ ] 文件命名小写
- [ ] requirements 瘦身
- [ ] `pyproject.toml`
- [ ] unit tests
- [ ] `PROVENANCE.md`

### Definition of Done

```bash
pytest
ruff check .
mypy src
```

全部通过。

---

## Phase 1：领域化数据模型

### 目标

从 generic CSV RAG 迁移到科研实体系统。

### 任务

- [ ] SQLAlchemy models
- [ ] Alembic
- [ ] Paper
- [ ] Taxon
- [ ] Compound
- [ ] Evidence
- [ ] OmicsAssociation
- [ ] CandidateLink

### DoD

可导入 demo fixtures，并通过 API 查询。

---

## Phase 2：Literature Evidence RAG

### 目标

实现带 provenance 的文献检索。

### 任务

- [ ] literature adapter
- [ ] paper/chunk schema
- [ ] structured chunking
- [ ] dense retrieval
- [ ] BM25
- [ ] hybrid
- [ ] reranker
- [ ] metadata filters
- [ ] source tracing

### DoD

任一搜索结果可追溯：

```text
chunk → paper → DOI/source
```

---

## Phase 3：Taxonomy-aware Evidence

### 目标

形成项目首个真正差异化能力。

### 任务

- [ ] taxon normalization
- [ ] strain/species/genus parsing
- [ ] taxonomy distance
- [ ] evidence tier
- [ ] policy tests

### DoD

系统不得把 genus-level evidence 写成 strain-level conclusion。

---

## Phase 4：Natural Product Linking

### 目标

连接微生物与天然产物记录。

### 任务

- [ ] natural product adapter
- [ ] compound normalization
- [ ] producer taxon linking
- [ ] bioactivity records
- [ ] candidate links
- [ ] conflict handling

### DoD

可完成：

```text
Taxon → Candidate NP → Evidence Tier → Source
```

---

## Phase 5：Own-data-to-literature

### 目标

将申请者自己的多组学经验真正写入系统。

### 任务

- [ ] own-omics CSV schema
- [ ] import validation
- [ ] raw label preservation
- [ ] entity resolution
- [ ] association storage
- [ ] candidate ranking
- [ ] validation suggestions

### DoD

输入一份 16S–metabolite association CSV，输出外部证据候选表。

---

## Phase 6：Evidence-grounded Writer

### 目标

让 LLM 输出可审计科研答案。

### 任务

- [ ] Pydantic answer schema
- [ ] claim-level citation
- [ ] refusal states
- [ ] constraint validator
- [ ] audit view

### DoD

每个事实 claim 均绑定 evidence ID。

---

## Phase 7：Evaluation

### 目标

从 Demo 变成可评估 AI 项目。

### 任务

- [ ] 100-query benchmark
- [ ] relevance labels
- [ ] Recall@K
- [ ] MRR
- [ ] nDCG
- [ ] ablation
- [ ] citation precision
- [ ] faithfulness
- [ ] abstention accuracy
- [ ] taxonomy safety

### DoD

生成：

```text
reports/eval/latest/
```

---

## Phase 8：申博 Demo Package

### 目标

形成导师可直接查看的成果。

### 任务

- [ ] 3-minute demo
- [ ] architecture figure
- [ ] 3 case studies
- [ ] evaluation table
- [ ] limitations
- [ ] future work
- [ ] clean README
- [ ] reproducible setup

### DoD

新用户按 README 能运行 demo。

---

# 22. 建议的三个 Demo Case

## Case 1：Root injury → microbial candidate → external evidence

来自申请者真实研究语境：

```text
Mechanical root injury
↓
taxon enrichment
↓
metabolite association
↓
external plant–microbe evidence
↓
candidate natural-product links
```

重点展示：

- own data；
- evidence tier；
- limitations。

---

## Case 2：Rhizosphere Streptomyces → biocontrol / natural products

展示：

- rhizosphere taxon；
- literature；
- natural product records；
- taxonomy distance；
- biological activity。

这是与目标课题组方向最直观的案例之一。

---

## Case 3：必须拒答

问题：

> “16S 检测到 Streptomyces，是否证明样本产生某特定抗生素？”

系统必须拒绝强结论。

这能体现：

- 科研严谨性；
- hallucination control；
- taxonomy-aware reasoning。

---

# 23. README 首页建议

```markdown
# RhizoNP Navigator

RhizoNP Navigator is an evidence-grounded retrieval and candidate-linking
system for plant–microbe interactions and microbial natural products.

It connects:
- user-provided multi-omics associations,
- scientific literature,
- structured biological entities,
- microbial natural-product records,

while explicitly modeling:
- taxonomic distance,
- evidence directness,
- chemical identification confidence,
- provenance,
- insufficient evidence.

## What makes it different?

1. Taxonomy-aware evidence grading
2. Own-data-to-literature linking
3. Claim-level provenance
4. Scientific refusal policies
5. Retrieval and grounding evaluation
```

不要写：

```text
AI-powered revolutionary drug discovery platform
```

这会降低可信度。

---

# 24. Codex 实施规则

将本文件交给 Codex 时，要求遵守：

## 24.1 禁止 Big Bang Rewrite

每阶段独立：

```text
Phase 0
→ tests
→ commit

Phase 1
→ tests
→ commit
```

---

## 24.2 每个阶段先审计后修改

Codex 必须：

1. 读取当前仓库；
2. 列出将保留文件；
3. 列出将删除/移动文件；
4. 给出风险；
5. 再实施。

---

## 24.3 不得虚构数据源能力

禁止：

- 未实现 API 却写“已集成”；
- 无 benchmark 却写“提升 15%”；
- 无结构模型却写“multimodal AI”；
- 无 agent loop 却写“autonomous agent”。

---

## 24.4 每个新能力必须有测试

例如：

```text
taxonomy-aware
→ policy test

citation
→ citation coverage test

delete
→ multi-chunk delete test
```

---

# 25. 可直接交给 Codex 的分阶段任务提示词

## Prompt A：Phase 0

```text
请以当前仓库为基线，严格按照 RHIZONP_NAVIGATOR_MIGRATION_PLAN.md 的 Phase 0 执行安全与工程基线修复。

要求：
1. 先审计，不要立即重写。
2. 保留现有核心功能：CSV -> Embedding -> FAISS -> rerank -> UUID -> PostgreSQL -> LLM。
3. 移除所有真实密钥与密码，改为 pydantic-settings + .env.example。
4. 修正 bge-reranker-v2-m3 的适配实现。
5. 修复 delete_file_from_knowledge_vector_db 只删除首个 chunk 的问题。
6. 消除 Windows 绝对路径。
7. 统一 Python 文件命名。
8. 建立 pyproject.toml，删除未使用依赖。
9. 新增 pytest 测试。
10. 建立 docs/PROVENANCE.md，真实说明 upstream 与新增贡献。

完成后输出：
- changed files
- preserved behavior
- tests
- known limitations
- next phase blockers

不要开始 Phase 1。
```

---

## Prompt B：Phase 1

```text
在 Phase 0 已通过全部测试的前提下，实现 RHIZONP_NAVIGATOR_MIGRATION_PLAN.md Phase 1。

要求：
- PostgreSQL
- SQLAlchemy 2
- Alembic
- Paper
- Taxon
- Compound
- NaturalProductRecord
- Dataset
- OmicsAssociation
- Evidence
- CandidateLink

必须：
1. schema 有唯一约束和索引；
2. provenance 使用 JSONB；
3. 不删除旧流程；
4. 新增 migration；
5. 新增 repository layer；
6. 单元与集成测试。

不要接入真实外部数据库。
```

---

## Prompt C：Phase 2–3

```text
实现文献证据检索和 taxonomy-aware evidence。

重点：
1. literature ingestion interface
2. structured chunk metadata
3. dense retrieval
4. BM25
5. hybrid retrieval
6. reranking
7. source provenance
8. taxonomy normalization
9. same_strain/same_species/same_genus distance
10. evidence tier policy

必须加入科研安全测试：
- genus-level evidence cannot claim strain-level production
- unresolved taxon cannot produce strong candidate link
```

---

## Prompt D：Phase 5

```text
实现 Own-data-to-literature。

输入：
- taxa.csv
- metabolites.csv
- associations.csv

要求：
1. 保留 raw label；
2. 实体解析状态可见；
3. unresolved 不得强制映射；
4. 导入 omics_associations；
5. 为每条 association 检索外部 evidence；
6. 输出 candidate matrix；
7. 支持 INSUFFICIENT_EVIDENCE；
8. 生成可审计报告。
```

---

# 26. 申博材料最终表述建议

完成 Phase 0–5 后可写：

> **RhizoNP Navigator：面向植物—微生物互作与微生物天然产物的证据增强检索系统**
> 基于 Python、FAISS、PostgreSQL 与 LLM 构建跨内部多组学结果、科研文献和结构化天然产物记录的证据检索与候选关联系统；设计 taxonomy-aware evidence grading，显式区分菌株、物种和属水平证据，避免由 16S 群落观察直接外推天然产物生产能力；实现 hybrid retrieval、reranking、来源追踪、证据不足拒答及 own-data-to-literature 工作流，用于将 16S–代谢物关联结果连接到可验证的外部机制证据。

完成 Phase 7 后再增加真实指标：

> 在自建 benchmark 上报告 Recall@K、MRR、nDCG、citation precision 和 abstention accuracy。

**只有真实跑出结果后才能填写数值。**

---

# 27. 成功标准

项目成功不以“功能多”为标准，而以以下问题回答“是”为标准：

- [ ] 是否从申请者真实根际多组学问题出发？
- [ ] 是否自然连接微生物天然产物？
- [ ] 是否有 own-data-to-literature？
- [ ] 是否区分 strain/species/genus？
- [ ] 是否区分 LC-MS feature 与 confirmed compound？
- [ ] 是否能拒答？
- [ ] 是否每个 claim 可追溯？
- [ ] 是否有 retrieval benchmark？
- [ ] 是否有 ablation？
- [ ] 是否有 scientific policy tests？
- [ ] 是否能在 Linux 重现？
- [ ] 是否无密钥泄漏？
- [ ] 是否真实说明个人贡献边界？
- [ ] 是否避免把项目包装成未实现的 autonomous agent？

达到这些标准后，项目才真正从：

```text
RAG engineering demo
```

迁移为：

```text
AI-for-Science evidence system
```

---

# 28. 推荐最终路线

最推荐顺序：

```text
P0 修复原仓库
  ↓
P1 科研实体 Schema
  ↓
P2 文献证据检索
  ↓
P3 Taxonomy-aware Evidence
  ↓
P4 Natural Product Linking
  ↓
P5 Own-data-to-literature
  ↓
P6 Grounded Writer
  ↓
P7 Evaluation
  ↓
P8 申博 Demo
```

不要改变顺序。

其中真正决定项目是否“加分”的不是 UI，也不是 LLM 模型大小，而是：

```text
Taxonomy-aware
+
Evidence-aware
+
Own-data-to-literature
+
Evaluation
```

---

# 29. 参考依据与实施时需重新核对的官方来源

> 以下来源用于确定项目方向与数据接入策略。外部数据接入前必须再次核对最新 API、许可、下载与再分发条款。

1. Qin Lab Research
   https://zhiweiqin.com/research

2. Qin Lab Publication
   https://zhiweiqin.com/publication-1

3. Natural Products Atlas
   https://www.npatlas.org/

4. MIBiG
   https://mibig.secondarymetabolites.org/

5. NCBI Entrez Programming Utilities
   https://www.ncbi.nlm.nih.gov/books/NBK25501/

6. Crossref REST API
   https://www.crossref.org/documentation/retrieve-metadata/rest-api/

---

# 30. 最后一条工程原则

> **不要为了“更像导师方向”而抹掉原来的研究身份。**

RhizoNP Navigator 最有价值的地方正是：

```text
申请者真实的根际代谢组 / 16S 经验
        +
已有 RAG / Embedding / PostgreSQL 工程经验
        +
微生物天然产物知识连接
        +
严谨的证据边界
```

这四部分同时存在，项目才具有真正的个人辨识度。
