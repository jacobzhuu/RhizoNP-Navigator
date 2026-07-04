# RhizoNP Navigator 重构计划

## 目标

将当前 RhizoNP-Navigator 仓库从 RAGNavigator 原型分阶段重构为可复现、可评估、跨平台的 AI-for-Science 证据增强检索系统。以 `RHIZONP_NAVIGATOR_MIGRATION_PLAN.md` 为核心依据，避免不可审计的 Big Bang Rewrite。

## 当前阶段

Phase 0: 工程基线、安全、可复现性与跨平台修复。

## 阶段状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| Phase 0 | in_progress | 本地工程基线已提交；远端 CI/secret scanning 和凭据轮换仍需外部处理 |
| Phase 1 | in_progress | SQLAlchemy/Alembic 领域模型 baseline 已开始 |
| Phase 2 | pending | 文献证据检索与 provenance |
| Phase 3 | pending | Hybrid retrieval、reranking、taxonomy-aware grading |
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

## Phase 1 剩余项

- [ ] 在 PostgreSQL 容器中实际运行 Alembic migration；当前环境 Docker daemon 未运行。
- [ ] API 查询尚未实现。
- [ ] 尚未建立 SQLAlchemy 与旧 PostgreSQL UUID 回查流程的集成边界。

## 决策原则

- 保留可复用的 Embedding、FAISS、Reranker、PostgreSQL、LLM 联合分析能力。
- 禁止写死平台专属路径、用户目录、模型目录、数据库地址或 shell 假设。
- 新增能力必须有真实代码与测试支撑。
- 证据不足时必须支持明确的 `INSUFFICIENT_EVIDENCE` 等状态。
- 不把属水平 16S 证据外推为菌株级天然产物生产。
- 不把未知 LC-MS feature 当作确证化合物。
- 不把相关性写成因果关系。
