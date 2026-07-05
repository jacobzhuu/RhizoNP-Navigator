# RhizoNP Navigator 审计发现

## 迁移方案摘要

- 项目定位：RhizoNP Navigator 是面向植物-微生物互作与微生物天然产物的 evidence-grounded retrieval / candidate-linking 系统，不是通用天然产物聊天机器人。
- 迁移路线必须保持分阶段：Phase 0 工程基线 -> Phase 1 领域数据模型 -> Phase 2 文献证据检索 -> Phase 3 taxonomy-aware evidence -> Phase 4 natural product linking -> Phase 5 own-data-to-literature -> Phase 6 grounded writer -> Phase 7 evaluation -> Phase 8 demo/package。
- 必须保留并逐步封装原有能力：CSV -> Embedding -> FAISS -> Reranker -> UUID -> PostgreSQL -> LLM。
- 科研安全边界：属水平 16S 不得外推到菌株级天然产物生产；未知 LC-MS feature 不得宣称为确证化合物；相关性不得写成因果；证据不足必须可返回 `INSUFFICIENT_EVIDENCE`。
- Phase 0 重点：secrets、`.env.example`、reranker wrapper、multi-chunk vector deletion、跨平台路径、文件命名、依赖瘦身、`pyproject.toml`、unit tests、`docs/PROVENANCE.md`。
- Phase 0 Definition of Done：`pytest`、`ruff check .`、`mypy src` 全部通过；当前仓库可能需要先建立这些检查的最低可运行基线。

## 仓库现状

- Git：当前在 `main...origin/main`，迁移方案和三个工作文件为未跟踪文件；原始仓库最近提交为 README 更新。
- 结构：源码仅有 `src/Config.py`、`src/Embedding.py`、`src/GetAnswer.py`、`src/MakeVectorDB.py`、`src/Main.py`、`src/DownloadModel.py`；无 `tests/`、无 `pyproject.toml`、无 docs 目录。
- 数据：`data/input.csv`、`data/input.xlsx`、`data/faiss_all_acge/files/input.csv` 已被 Git 跟踪；FAISS `index.faiss`/`index.pkl` 在 `.gitignore` 中但当前工作树未显示。
- 配置：存在 `.gitignore`，但未忽略 `.env*`；README 中列出小写文件名，实际源码是大写文件名。
- 依赖：`requirements.txt` 是整环境 freeze，包含 Jupyter、Chroma、Windows-only 包等大量当前代码未直接使用依赖。
- 测试：没有任何单元测试或 CI 配置。

## Phase 0 差距与风险

- P0-1 secrets：`src/Config.py` 有 API-key-looking 字符串；`src/GetAnswer.py` 有 PostgreSQL 明文密码；`src/Embedding.py` 注释中也有 API-key-looking 字符串。需要改为环境变量并提醒 rotate/revoke。
- P0-2 reranker：`GetAnswer.py` 配置 `bge-reranker-v2-m3`，但实际使用 `FlagLLMReranker`；应改为 `FlagReranker` 并加协议/适配层。
- P0-3 删除逻辑：`delete_file_from_knowledge_vector_db` 遇到第一个 source basename 匹配就 `break`，多 chunk 文件只删一个 chunk，且同名不同路径可能误删。
- P0-4 路径：`Config.py`/`Embedding.py` 存在 Windows 绝对路径；`MakeVectorDB.py`/`Main.py` 用 `os.path` 拼接路径，可先用 `pathlib` 修复关键路径。
- P0-5 文件命名：README 与实际大小写不一致；macOS 上 case-only rename 有风险，本轮先不做不可回滚重命名。
- P0-6 依赖：需要从 freeze 缩减为项目直接依赖。
- P0-7 provenance：缺少 `docs/PROVENANCE.md`。
- 高优先实施顺序：配置/secrets -> embedding 懒加载和跨平台路径 -> reranker adapter -> multi-chunk delete -> tests/tooling/docs。

## 错误记录

| 错误 | 尝试次数 | 处理 |
| --- | ---: | --- |
| `python -m pytest` 初次失败：环境缺少 pytest | 1 | 安装 `pytest`、`ruff`、`mypy` 后重试 |
| pytest 收集失败：环境缺少 `pydantic_settings` | 1 | 安装 `pydantic-settings` 后重试 |
| `ruff check .` 初次失败：导入排序、typing、`zip(strict=...)` | 1 | 运行 `ruff check . --fix` 并人工补 `strict=True` |
| `mypy src` 初次失败：`Main.py` 示例 query 推断为 `None` 值字典 | 1 | 标注 `query_dict: dict[str, str]`，并将 SQL 空结果规范化为 `[]` |

## 本轮验证

- `python -m pytest`：9 passed。
- `ruff check .`：All checks passed。
- `mypy src`：Success, no issues found in 6 source files。
- `python -m compileall src tests`：通过。
- `git grep -nE 'sk-|password\s*=|api_key\s*=|C:\\|D:\\|86133|013777'`：tracked files 无匹配。

## Phase 0 第二批验证

- `python -m scripts.check_no_secrets`：通过，No committed secret-looking values found。
- `python -m pytest`：12 passed。
- `ruff check .`：All checks passed。
- `mypy src`：Success, no issues found in 6 source files。
- `make check`：通过，串联 secret scan、ruff、mypy、pytest。
- `docker compose config`：通过，Compose 文件可解析。
- `python -m compileall src tests scripts`：通过。
- `git diff --check`：通过。

## Phase 0 第二批新增发现

- 当前 CI 为轻量跨平台检查：只安装 `pydantic-settings`、`pytest`、`ruff`、`mypy`，不在 Windows/macOS/Linux CI 中安装 FAISS/FlagEmbedding 等重依赖，避免把模型/平台 wheel 问题混入 Phase 0 单元检查。
- Docker Compose 使用环境变量插值提供本地开发默认 PostgreSQL 凭据；这些不是生产凭据，`docs/SECURITY.md` 已说明需要在 `.env` 中覆盖且不得用于共享服务器或生产数据。

## Phase 0 文件命名迁移

- macOS 常见大小写不敏感文件系统不能在同一目录可靠保留 `Config.py` 和 `config.py` 两个文件；直接 case-only rename 风险较高。
- 采取保守迁移：新增 `src/rhizonp/` Python 包，当前实现放入 `config.py`、`embedding.py`、`get_answer.py`、`make_vector_db.py`、`download_model.py`、`main.py`。
- 原大写模块保留为 thin compatibility wrappers，避免破坏用户已有脚本。
- 项目内部测试和 README 推荐入口已切换到 `rhizonp.*` 小写包路径。
- 新增 legacy wrapper 测试，验证旧模块仍 re-export 新包 API。

## Phase 1 领域模型 baseline

- 新增 `src/rhizonp/domain/models.py`，用 SQLAlchemy 2 declarative metadata 表达 Phase 1 核心实体。
- 新增 `src/rhizonp/storage/postgres.py` 和 `repositories.py`，提供 engine/session/repository 最小基线。
- 新增 Alembic 配置和 `migrations/versions/0001_domain_schema.py`。
- JSON 字段在 PostgreSQL 使用 JSONB，在 SQLite 测试中使用 JSON variant。
- UUID 由应用层默认生成，保证 SQLite 单元测试和跨平台本地开发可运行；后续可在 PostgreSQL migration 中增加数据库端 UUID default。
- `metadata` 数据库列在 Python 属性中命名为 `observation_metadata` / `association_metadata`，避免冲突 SQLAlchemy reserved attribute。

## Phase 1 验证

- `python -m pytest`：23 passed。
- `make check`：通过，包含 secret scan、ruff、mypy、pytest。
- `mypy src`：Success, no issues found in 20 source files。
- `DATABASE_URL=sqlite+pysqlite:////tmp/rhizonp_alembic_test.db alembic upgrade head`：通过。
- `DATABASE_URL=sqlite+pysqlite:////tmp/rhizonp_alembic_test.db alembic current`：`0001_domain_schema (head)`。
- `DATABASE_URL=sqlite+pysqlite:////tmp/rhizonp_fixture_cli.db python -m scripts.load_demo_fixtures`：通过，导入 synthetic Phase 1 fixture。

## Phase 1 错误记录

| 错误 | 尝试次数 | 处理 |
| --- | ---: | --- |
| `git push -u origin codex/phase-0-baseline` 失败：无法读取 GitHub HTTPS 用户名 | 1 | 记录为外部认证 blocker，继续本地 Phase 1 |
| Alembic 初次运行失败：`ModuleNotFoundError: No module named 'rhizonp'` | 1 | 将 `alembic.ini` 的 `prepend_sys_path` 改为 `src` |
| `python -m scripts.load_demo_fixtures` 初次失败：src-layout 下脚本无法导入 `rhizonp` | 1 | 脚本用 `pathlib` 将仓库 `src/` 加入 `sys.path` |
| `docker compose up -d postgres` 失败：Docker daemon 未运行 | 1 | 记录为本地环境 blocker；SQLite migration/fixture 验证已通过 |
| `git push origin HEAD:main` 失败：无法读取 GitHub HTTPS 用户名 | 1 | 记录为认证 blocker；本地 Phase 1 commit 已创建 |

## Phase 1 fixture 边界

- `data/fixtures/phase1_demo.json` 是 synthetic fixture，用于测试 Phase 1 schema/import/query path。
- fixture 明确标记 `fixture: true`、`not_real_literature`、`not_real_database_record` 和 `not_real_experiment`。
- fixture 中的 Streptomyces 只作为 genus-level synthetic signal；候选关系状态为 `PARTIALLY_SUPPORTED`，并保留 genus-level limitation。
- fixture 中的 `Feature_M123` 保持为 C4 unknown feature，不被转成确证化合物。

## Phase 1 API 查询层

- 新增 `rhizonp.api` 作为 Phase 1 最小只读 API；端点只查询已入库实体，不启动 RAG、Agent、多模态或外部数据接入。
- API 入口为 `rhizonp.api:app` / `create_app()`；数据库 session 通过 `DATABASE_URL` 懒加载，测试可覆盖 `get_session`。
- 当前端点覆盖 health、taxon、compound、taxon evidence、taxon candidate links、dataset omics associations。
- API 测试使用内存 SQLite + synthetic fixture，验证 evidence tier、`PARTIALLY_SUPPORTED`、genus-level limitation 和 `correlation_not_causation` 元数据均可通过 API 返回。

## Phase 1 独立 DoD 审计

- 科研实体 schema：`rhizonp.domain.models` 和 `0001_domain_schema` 覆盖 Paper、Taxon、Compound、NaturalProductRecord、Dataset、OmicsObservation、OmicsAssociation、EvidenceItem、CandidateLink。
- Repository layer：`rhizonp.storage.repositories` 覆盖实体 CRUD baseline 和领域查询方法。
- Synthetic fixture ingestion：`data/fixtures/phase1_demo.json` 与 `load_phase1_demo_fixture()` 可导入 1 paper、1 taxon、1 compound、1 NP record、1 dataset、2 observations、1 association、1 evidence item、1 candidate link。
- 最小只读 API：`rhizonp.api` 可查询 fixture 中的 taxon、compound、evidence、candidate links 和 omics associations。
- Migration：SQLite `alembic upgrade head` / `current` 通过；PostgreSQL offline SQL 生成通过并包含 JSONB；PostgreSQL 容器实跑未完成，原因是本机 Docker daemon 未运行。
- Tests：`make check` 通过，27 tests passed，保留原有 23 tests 并新增 4 个 API tests。
- Cross-platform：路径通过 `pathlib`/env/config；CI matrix 覆盖 Linux/macOS/Windows 轻量检查；实际远端 CI 仍需 push 后验证。

## Phase 2 范围审计

- 迁移方案 Phase 2 目标是带 provenance 的文献检索；DoD 是搜索结果可追溯 `chunk -> paper -> DOI/source`。
- 当前实现选择 Phase 2 provenance baseline：schema、synthetic adapter、structured chunking、BM25 本地检索和 persisted source trace。
- 未接入真实外部文献源，因此不需要也不能声称 PubMed/Crossref/OpenAlex/full-text integration 已完成。
- 未实现 dense retrieval、hybrid fusion 或 literature reranker，因此 Phase 2 仍是 in-progress。
- Phase 3 的 taxonomy-aware evidence grading 未开始；本轮不实现 evidence tier policy 自动判定。

## Phase 2 provenance baseline 验证

- `paper_chunks` 存储 section、paragraph index、char span、source hash 和 chunk metadata。
- `retrieval_runs` / `retrieval_results` 记录 query、filters、parameters、rank、score、matched terms 和 trace provenance。
- Synthetic literature fixture 导入 1 个 paper 和 6 个 chunks；fixture 明确 `not_real_literature`。
- BM25 search 可以按 year、section、taxa 过滤，并返回 DOI/source URL trace。
- `POST /api/v1/search` 支持本地 `bm25`、`dense`、`hybrid` 和 `hybrid_rerank` 模式。
- Dense baseline 使用 deterministic hashing vector，只用于可复现接口和测试；不声称具备生产级语义检索质量。
- Hybrid baseline 记录 BM25、dense、normalized score 和 weights。
- Rerank baseline 使用本地 lexical-overlap reranker，并保持与现有 `score(query, passages)` reranker protocol 兼容。
- 当前仍不调用外部 API、embedding 模型或 cross-encoder reranker。
- 本地 baseline 不替代后续 model-backed embedding、FAISS literature index 或 BGE/cross-encoder literature reranker；这些仍需要单独实现和评估。
