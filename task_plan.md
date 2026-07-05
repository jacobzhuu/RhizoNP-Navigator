# RhizoNP Navigator 重构计划

## 目标

将当前 RhizoNP-Navigator 仓库从 RAGNavigator 原型分阶段重构为可复现、可评估、跨平台的 AI-for-Science 证据增强检索系统。以 `RHIZONP_NAVIGATOR_MIGRATION_PLAN.md` 为核心依据，避免不可审计的 Big Bang Rewrite。

## 当前阶段

Phase 2: 文献 provenance baseline 与本地检索。

## 阶段状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| Phase 0 | complete_local | 本地 DoD 通过；远端 CI/secret scanning、Git 历史清理和凭据轮换仍需外部处理 |
| Phase 1 | complete_local | Schema/migration/repository/fixture/API 与测试已通过本地验收；PostgreSQL 容器实跑受 Docker daemon 限制 |
| Phase 2 | in_progress | PubMed adapter, corpus workflow, offline retrieval eval added; production benchmark on live corpus still pending |
| Phase 3 | pending | taxonomy-aware grading |
| Phase 4 | pending | natural-product linking |
| Phase 5 | pending | own-data-to-literature |
| Phase 6 | pending | grounded writer 与拒答机制 |
| Phase 7 | pending | 系统评测 |
| Phase 8 | pending | 发布、文档与长期维护 |

## Phase 0 初始任务

- [x] 完整阅读迁移方案。
- [x] 审计目录结构、依赖、配置、测试、Git 状态。
- [x] 对照迁移方案列出 Phase 0 差距与风险。
- [x] 优先修复安全且可回滚的工程基线问题。
- [x] 运行相关测试与检查。
- [x] 汇报 changed files、preserved behavior、tests、known limitations、remaining blockers、next recommended step。

## Phase 0 本轮已完成

- [x] 移除工作树中的 API-key-looking 字符串和 PostgreSQL 明文密码。
- [x] 新增 `.env.example`，配置从环境变量读取。
- [x] 将配置集中到 `Settings` / `get_settings()`。
- [x] 去除 Windows 绝对模型路径，改用模型 ID 或环境变量。
- [x] Embedding 改为懒加载，避免 import 时加载大模型。
- [x] Reranker 改为 `RerankerProtocol` + `BGEReranker`，使用 `FlagReranker` 适配 `bge-reranker-v2-m3`。
- [x] 修复向量库删除只删第一个 chunk 的问题。
- [x] 新增 `pyproject.toml`、精简 `requirements.txt`。
- [x] 新增 `docs/PROVENANCE.md`。
- [x] 新增 Phase 0 单元测试。
- [x] 新增 repo-local secret scanning 脚本。
- [x] 新增 GitHub Actions CI，覆盖 Linux/macOS/Windows 的 Phase 0 轻量检查。
- [x] 新增 Makefile 本地检查入口。
- [x] 新增 Dockerfile 与 Docker Compose PostgreSQL/app 基线。
- [x] 新增 `docs/SECURITY.md`。
- [x] 新增 `src/rhizonp/` 小写包承载当前实现。
- [x] 保留 `Config.py`、`Embedding.py`、`GetAnswer.py`、`MakeVectorDB.py`、`DownloadModel.py`、`Main.py` 作为 legacy 兼容 wrapper。
- [x] 更新测试和 README 使用 `rhizonp.*` 小写包路径。
- [x] 在 `codex/phase-0-baseline` 分支创建 Phase 0 baseline 提交。

## Phase 0 剩余项

- [ ] 真实凭据需要在外部服务中 rotate/revoke；代码删除不能撤销历史泄漏。
- [ ] legacy 大写 wrapper 仍保留；后续可在用户脚本迁移后删除。
- [ ] CI workflow 已添加但尚未在 GitHub 远端运行验证；当前环境缺 GitHub HTTPS 凭据，无法 push。
- [ ] Docker Compose 配置语法已验证，但尚未执行完整镜像 build/test。
- [ ] 尚未完成 Git 历史清理或 GitHub secret scanning 平台配置。

## Phase 1 当前完成

- [x] 新增 SQLAlchemy 2 ORM metadata。
- [x] 新增 Alembic 配置和 `0001_domain_schema` 初始 migration。
- [x] 新增 `Paper`、`Taxon`、`Compound`、`NaturalProductRecord`。
- [x] 新增 `Dataset`、`OmicsObservation`、`OmicsAssociation`。
- [x] 新增 `EvidenceItem`、`CandidateLink`。
- [x] 新增 session/repository baseline。
- [x] 新增 `docs/DATA_MODEL.md`。
- [x] 新增 SQLite ORM/repository tests 和 Alembic head test。
- [x] 增加 repository layer 的领域化查询方法。
- [x] 增加 synthetic demo fixture 和导入脚本。
- [x] 增加 fixture import 测试和 CLI 临时 SQLite 验证。
- [x] 增加最小只读 FastAPI 查询层。
- [x] 增加 API 查询 synthetic fixture 的单元测试。

## Phase 1 剩余项

- [x] 运行完整检查并独立复核 Phase 1 DoD。
- [x] 形成单独 Phase 1 commit。
- [ ] push 到 `origin/main`；当前环境缺 GitHub HTTPS 凭据，推送失败。
- [ ] 在 PostgreSQL 容器中实际运行 Alembic migration；当前环境 Docker daemon 未运行。
- [ ] 尚未建立 SQLAlchemy 与旧 PostgreSQL UUID 回查流程的集成边界。

## Phase 2 当前完成

- [x] 重新审计迁移方案 Phase 2 范围。
- [x] 明确不接真实外部文献源、不虚构 dense/hybrid/reranker。
- [x] 新增 `paper_chunks`、`retrieval_runs`、`retrieval_results` ORM schema。
- [x] 新增 Alembic `0002_literature_provenance` migration。
- [x] 新增 synthetic literature adapter interface baseline。
- [x] 新增结构化 chunking，保留 section、paragraph、char span、source hash 和 metadata。
- [x] 新增 synthetic Phase 2 literature fixture 与导入脚本。
- [x] 新增本地 BM25 search 和 persisted retrieval provenance。
- [x] 新增 deterministic dense-vector literature retrieval baseline。
- [x] 新增 BM25 + dense hybrid fusion baseline。
- [x] 新增 local reranker protocol integration 和 lexical-overlap reranker baseline。
- [x] 新增 `LiteratureVectorIndex` protocol 与可 JSON 持久化的 `InMemoryLiteratureVectorIndex` baseline。
- [x] `POST /api/v1/search` 支持 `bm25`、`dense`、`hybrid`、`hybrid_rerank`。
- [x] 增加 column-backed 与 metadata-backed search filters。
- [x] 新增 `POST /api/v1/search`，返回 chunk→paper→DOI/source trace。
- [x] 新增单元/API 测试覆盖 chunking、ingestion、retrieval、API trace。
- [x] 新增 literature embedding adapter boundary（hashing + optional HuggingFace）。
- [x] 新增 optional FAISS `LiteratureVectorIndex` adapter。
- [x] 新增 literature reranker adapter boundary（none / lexical / optional BGE）。
- [x] 新增 `docs/LITERATURE_SOURCES.md` 与 synthetic adapter contract tests。

## Phase 2 剩余项

- [x] 形成 Phase 2 provenance baseline 单独 commit。
- [x] 形成 Phase 2 local retrieval baseline 单独 commit。
- [x] literature embedding adapter boundary（hashing + optional HuggingFace）。
- [x] optional FAISS literature vector index adapter。
- [x] literature reranker adapter boundary（none / lexical / optional BGE）。
- [x] source adapter 边界文档与 synthetic adapter contract tests。
- [x] 真实外部 PubMed/NCBI E-utilities source adapter（metadata-only）。
- [x] bounded domain corpus fetch/ingest workflow。
- [x] offline Phase 2 retrieval benchmark framework（explicit synthetic gold labels）。
- [ ] 基于 live PubMed corpus 的 production retrieval benchmark 与 model-backed 系统评估。
- [ ] Phase 2 完整 DoD 终验（含可选 FAISS 实装环境 parity 验证）。
- [ ] push 到 origin/main；当前环境缺 GitHub HTTPS 凭据。

## 决策原则

- 保留可复用的 Embedding、FAISS、Reranker、PostgreSQL、LLM 联合分析能力。
- 禁止写死平台专属路径、用户目录、模型目录、数据库地址或 shell 假设。
- 新增能力必须有真实代码与测试支撑。
- 证据不足时必须支持明确的 `INSUFFICIENT_EVIDENCE` 等状态。
- 不把属水平 16S 证据外推为菌株级天然产物生产。
- 不把未知 LC-MS feature 当作确证化合物。
- 不把相关性写成因果关系。
