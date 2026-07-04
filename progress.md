# RhizoNP Navigator 工作进度

## 2026-07-05

- 初始化持久化工作文件：`task_plan.md`、`findings.md`、`progress.md`。
- 当前目标：完整阅读迁移方案，审计仓库实际状态，并开始 Phase 0 中最高优先级且安全的修复。
- 已完整阅读 `RHIZONP_NAVIGATOR_MIGRATION_PLAN.md`（2714 行）。
- 记录迁移方案核心约束：分阶段推进、保留原有检索链路、优先 Phase 0 工程基线和科研安全边界。
- 完成仓库审计：确认存在 secrets、Windows 绝对路径、错误 reranker wrapper、多 chunk 删除 bug、无测试、无 pyproject、依赖 freeze 和缺失 provenance 文档。
- 决策：本轮先做可回滚的 Phase 0 基线修复；不执行大小写文件重命名，避免 macOS case-only rename 风险。
- 完成 Phase 0 第一批修复：环境变量配置、`.env.example`、embedding 懒加载、`FlagReranker` adapter、多 chunk 删除、精简依赖、`pyproject.toml`、`docs/PROVENANCE.md`、README 更新和单元测试。
- 安装本地开发检查工具：`pytest`、`ruff`、`mypy`、`pydantic-settings`。
- 验证结果：`python -m pytest` 9 passed；`ruff check .` 通过；`mypy src` 通过；`python -m compileall src tests` 通过；tracked-file secret grep 无匹配。
- 同步 `pydantic-settings==2.14.2` 到 `requirements.txt` 与 `pyproject.toml`，并复跑 `pytest`、`ruff`、`mypy`、`git diff --check`，均通过。
- 继续 Phase 0：新增 `scripts/check_no_secrets.py`、`.github/workflows/ci.yml`、`Makefile`、`Dockerfile`、`.dockerignore`、`docker-compose.yml`、`docs/SECURITY.md`，并更新 README。
- 为 secret scanner 新增单元测试，修复对 Python 类型注解、YAML/env placeholder、运行时配置引用和测试夹具的误报。
- 验证结果：`python -m scripts.check_no_secrets` 通过；`python -m pytest` 12 passed；`ruff check .` 通过；`mypy src` 通过；`make check` 通过；`docker compose config` 通过；`python -m compileall src tests scripts` 通过；`git diff --check` 通过。
- 继续 Phase 0 文件命名迁移：新增 `src/rhizonp/` 小写包并把实现迁入包内；大写 legacy 文件改为兼容 wrapper；测试改用 `rhizonp.*` 包路径并新增 wrapper 兼容测试。
- 验证结果：`make check` 通过，包含 13 个 pytest；`mypy src` 覆盖 13 个源码文件；`python -m compileall src tests scripts` 通过；`git diff --check` 通过。
- 创建 `codex/phase-0-baseline` 分支，并将当前 Phase 0 基线整理为单个可审计提交：`chore: establish phase 0 baseline`。
- 尝试推送 `codex/phase-0-baseline` 到 origin，失败原因：当前环境无 GitHub HTTPS 凭据，无法读取用户名。
- 创建 `codex/phase-1-domain-models` 分支，开始 Phase 1。
- 新增 SQLAlchemy/Alembic 领域模型 baseline：Paper、Taxon、Compound、NaturalProductRecord、Dataset、OmicsObservation、OmicsAssociation、EvidenceItem、CandidateLink。
- 新增 storage session/repository baseline、Alembic 初始 migration、`docs/DATA_MODEL.md` 和数据库 schema 测试。
- Alembic 初次 SQLite 临时库验证因 src-layout import path 失败，已通过 `alembic.ini` 的 `prepend_sys_path = src` 修复。
- 验证结果：`make check` 通过，包含 21 个 pytest；`mypy src` 覆盖 18 个源码文件；SQLite 临时库 `alembic upgrade head` 和 `alembic current` 均通过；`docker compose config` 通过。
- 继续 Phase 1：新增领域化 repository 查询方法、`data/fixtures/phase1_demo.json` synthetic fixture、`rhizonp.ingestion.fixtures` loader 和 `scripts/load_demo_fixtures.py`。
- 修复脚本在 src-layout 下无法导入 `rhizonp` 的问题：`scripts/bootstrap_db.py` 和 `scripts/load_demo_fixtures.py` 使用 `pathlib` 将仓库 `src/` 加入 `sys.path`。
- 尝试 Docker PostgreSQL migration 验证失败：Docker daemon 未运行，无法拉起 `postgres:16`。
- 验证结果：`make check` 通过，包含 23 个 pytest；`mypy src` 覆盖 20 个源码文件；SQLite 临时库 Alembic migration 和 fixture CLI 导入均通过。
