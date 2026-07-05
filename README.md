# RhizoNP Navigator

本仓库正在从原 RAGNavigator 原型迁移为 RhizoNP Navigator：面向植物—微生物互作与微生物天然产物的证据增强检索系统。

当前 Phase 0 仍保留原型的核心链路：CSV -> Embedding -> FAISS -> Re-ranker -> UUID -> PostgreSQL -> LLM 分析。迁移目标、边界和后续阶段见 `RHIZONP_NAVIGATOR_MIGRATION_PLAN.md`。

## 目录结构

```
my_project/
├── README.md                # 项目说明文档
├── .env.example             # 本地环境变量模板，不包含真实密钥
├── pyproject.toml           # 项目与测试/静态检查配置
├── requirements.txt         # Python依赖列表
├── data/                    # 存放所有数据相关文件
│   ├── input.csv            # 原始CSV文件(用户手动放置)
│   ├── input.xlsx           # 示例原始Excel文件(可选)
│   └── faiss_all_acge/      # FAISS向量库文件夹(项目自动生成或更新)
│       ├── files/           # 存放已导入向量库的源文件副本
│       │   └── input.csv    # 由脚本拷贝过来的文件
│       ├── index.faiss      # FAISS索引文件
│       └── index.pkl        # FAISS索引辅助文件
├── src/                     # 项目的主要源码文件
│   ├── rhizonp/             # 小写 Python 包，承载当前实现
│   │   ├── config.py
│   │   ├── api/             # Phase 1 read-only API
│   │   ├── download_model.py
│   │   ├── embedding.py
│   │   ├── get_answer.py
│   │   ├── make_vector_db.py
│   │   └── main.py
│   ├── Config.py            # legacy 兼容 wrapper
│   ├── DownloadModel.py     # legacy 兼容 wrapper
│   ├── Embedding.py         # legacy 兼容 wrapper
│   ├── GetAnswer.py         # legacy 兼容 wrapper
│   ├── MakeVectorDB.py      # legacy 兼容 wrapper
│   ├── Main.py              # legacy 兼容 wrapper
│   └── ...
├── docs/
│   ├── DATA_MODEL.md        # Phase 1 领域数据模型
│   ├── PROVENANCE.md        # upstream 与迁移贡献边界
│   └── SECURITY.md          # secret 与数据安全边界
├── docker-compose.yml       # 本地 PostgreSQL/app 检查基线
├── Dockerfile               # app 容器基线
├── Makefile                 # 常用检查命令
└── tests/                   # Phase 0 单元测试
```

> 若你的实际工程结构略有不同，请在使用时做相应的路径调整。

---

## 1. 功能概述

1. **模型下载**  
   通过 `DownloadModel.py` 从 [ModelScope](https://modelscope.cn/) 下载所需的文本 Embedding 模型（如 `yangjhchs/acge_text_embedding`）和重排模型（如 `BAAI/bge-reranker-v2-m3`）到本地缓存。

2. **构建向量数据库**  
   运行 `MakeVectorDB.py`，将 `data/input.csv` 中的文本分块后，计算 Embedding 并存储在 FAISS 索引文件 (`index.faiss`, `index.pkl`) 中。这些文件会保存在 `faiss_all_acge` 文件夹下。

3. **检索与重排**  
   在 `GetAnswer.py` 中，通过向量检索 (FAISS) 找到最相似的文本块，再结合重排模型 (Re-ranker) 对结果进行进一步排序，得到最相关的文本片段。

4. **数据库查询与结果分析**  
   将检索到的 UUID 信息发送给 PostgreSQL 等数据库执行查询，并利用 LLM (例如 `ChatOpenAI` 或自定义 API) 进行过滤排序或生成更人性化的结果。

5. **主运行流程**  
   通过 `Main.py` 来串联上述所有步骤，实现从输入 Query 到最终结果的一体化处理。

---

## 2. 安装依赖

下面先介绍**直接使用 pip** 安装的方式；如果你需要使用 **Conda** 环境（尤其是名为 `rag` 的环境），请参考后续 [2.1 Conda 环境配置](#21-conda-环境配置) 的步骤。

### 2.0 直接使用 pip

```bash
pip install -r requirements.txt
```

这会安装所需 Python 包，包括但不限于：
- `langchain`
- `langchain_community`
- `modelscope`
- `sentence_transformers`
- `psycopg2`（如需连接 PostgreSQL）
- 以及其他通用依赖。

如遇到版本冲突，请结合报错信息手动修改。

开发检查工具：

```bash
pip install -e ".[dev]"
make check
```

### 2.1 本地配置

不要在源码中写入 API key、数据库密码或本机模型目录。复制 `.env.example` 为 `.env`，再填写本机配置：

```bash
cp .env.example .env
```

至少按需配置：

- `DEEPSEEK_API_KEY`
- `DATABASE_URL` 或 `POSTGRES_*`
- `EMBEDDING_MODEL`
- `RERANKER_MODEL`
- `VECTOR_DB_PATH`

如果旧仓库历史中出现过真实凭据，应在对应服务中 rotate/revoke；从当前文件删除并不能使已泄露凭据失效。

### 2.2 Conda 环境配置

若想在 VS Code 中使用 Conda 的 `rag` 环境来隔离并管理项目依赖，可按以下步骤进行：

1. **创建并激活 `rag` 环境**  
   ```bash
   # 在命令行中执行
   conda create -n rag python=3.10
   conda activate rag
   ```
   > 这里指定了 `python=3.10`，你也可以根据需要选择其他版本（如 3.9、3.11 等）。

2. **安装依赖**  
   在激活的 `rag` 环境下，执行：
   ```bash
   pip install -r requirements.txt
   ```
   这样就可以将所有依赖包装进 `rag` 环境。

3. **VS Code 中选择 `rag` 解释器**  
   - 打开 VS Code 后，按 `Ctrl + Shift + P`（Windows）或 `Cmd + Shift + P`（macOS），输入“Python: Select Interpreter”并回车；  
   - 在弹出的选项里，选择 `...\conda\envs\rag\python.exe`（见下图所示）；  
   - 确保 VS Code 的“终端”或“调试”使用的解释器都是这个 `rag` 环境，之后运行脚本就会使用已安装的依赖。
![选择Conda环境](VSCodeInterpreter.png)
*图片仅作示例，实际路径以你本地环境为准。*

---

## 3. 使用方法

### 3.1 下载模型

```bash
cd src
python -m rhizonp.download_model
```

执行成功后，将在本地 `~/.cache/modelscope/hub/...` 等目录下载并缓存指定模型。

### 3.2 构建向量数据库

1. **准备数据**  
   将你的原始 CSV 文件（例如 `input.csv`）放到 `data/` 目录下。  
   > **注意**：`data/input.csv` 是**原始的** CSV 数据。

2. **执行脚本**  
```bash
cd src
python -m rhizonp.make_vector_db
```
   - 脚本会将 `data/input.csv` 读入、进行 Embedding，并在 `data/faiss_all_acge/` 下生成：
     - `index.faiss`, `index.pkl` 等文件（真正存储向量索引的二进制和辅助文件）。
     - 将原始 `input.csv` **复制**到 `data/faiss_all_acge/files/` 文件夹中，用于记录哪些数据已导入索引。  
   - 也因此，你会看到项目中出现**两个 `input.csv`**，它们分别是：
     1. `data/input.csv`：**原始 CSV**（你自己放的）
     2. `data/faiss_all_acge/files/input.csv`：**被脚本拷贝过来的副本**（仅用于标记已成功导入的文件）  
   - **`index.faiss` 和 `index.pkl`** 才是真正的**向量库**文件，用于 FAISS 相似度搜索。

### 3.3 主脚本运行

```bash
cd src
python -m rhizonp.main
```

- 该脚本中示例演示了如何对某些 `query_dict` 进行近义词扩展 (`analyze_query`)、向量检索 (`get_knowledge_based_answer`)、数据库查询 (`query_uuid`) 以及结果排序 (`analyze_sql_results2`) 等操作。  
- 最终结果会打印在命令行中。

### 3.4 其他操作
- **增量添加 CSV 文件**  
  ```python
  from rhizonp.make_vector_db import add_to_knowledge_vector_db
  add_to_knowledge_vector_db("data/faiss_all_acge", "data/new_data.csv")
  ```
  这将把新文件 `new_data.csv` 读取并添加至已有向量库，并拷贝到 `files/` 文件夹。

- **删除已导入的文件**  
  ```python
  from rhizonp.make_vector_db import delete_file_from_knowledge_vector_db
  delete_file_from_knowledge_vector_db("data/faiss_all_acge", "data/input.csv")
  ```
  这将在向量库索引和 `files` 文件夹中删除对应内容。

旧命令 `python Main.py`、`python MakeVectorDB.py` 等仍保留为兼容入口，但新代码应优先导入 `rhizonp.*` 小写包模块。

### 3.5 本地 PostgreSQL / Docker

启动本地 PostgreSQL：

```bash
make db-up
```

运行容器内 Phase 0 测试：

```bash
make docker-test
```

关闭服务：

```bash
make db-down
```

### 3.6 Phase 1 demo fixture 与只读 API

Phase 1 新增 SQLAlchemy/Alembic 领域模型、synthetic demo fixture 和最小只读 FastAPI 查询层。该 API 只查询已入库实体，不接入真实外部数据源，不执行 RAG/Agent/多模态流程。

先配置 `DATABASE_URL` 并运行 migration：

```bash
alembic upgrade head
python -m scripts.load_demo_fixtures
```

ASGI 入口：

```python
from rhizonp.api import app
```

当前只读端点：

- `GET /api/v1/health`
- `GET /api/v1/taxa/{canonical_name}`
- `GET /api/v1/compounds/{canonical_name}`
- `GET /api/v1/taxa/{canonical_name}/evidence`
- `GET /api/v1/taxa/{canonical_name}/candidate-links`
- `GET /api/v1/datasets/{dataset_name}/omics-associations`

返回值会保留 `evidence_tier`、`status`、`rationale` 和 provenance 字段。Synthetic fixture 中的候选关系仍是 `PARTIALLY_SUPPORTED`，并明确保留 genus-level limitation；未知 LC-MS feature 仍作为 unknown feature，不会被 API 提升为确证化合物。

### 3.7 Phase 2 literature provenance baseline

Phase 2 当前实现本地 provenance/retrieval baseline：synthetic literature fixture、结构化 paper chunks、BM25 lexical search、deterministic dense-vector baseline、hybrid fusion、local rerank、retrieval run/result 记录和 search trace。它不接入 PubMed、Crossref、OpenAlex 或真实全文，也不声明已完成生产级 embedding/FAISS 文献索引或外部 reranker 模型集成。

导入 synthetic literature fixture：

```bash
alembic upgrade head
make load-literature-fixtures
```

最小 search API：

- `POST /api/v1/search`

`retrieval_mode` 可选：

- `bm25`
- `dense`
- `hybrid`
- `hybrid_rerank`

响应中的每条结果都包含：

```text
trace.chunk_id -> trace.paper_id -> trace.doi / trace.source_url
```

Phase 2 说明见 `docs/LITERATURE_PROVENANCE.md`。

### 3.8 数据库 Schema

Phase 1/2 引入 SQLAlchemy/Alembic 领域模型。当前 baseline 包括 `Paper`、`PaperChunk`、`RetrievalRun`、`RetrievalResult`、`Taxon`、`Compound`、`NaturalProductRecord`、`Dataset`、`OmicsObservation`、`OmicsAssociation`、`EvidenceItem` 和 `CandidateLink`。

运行 Alembic migration 需要先配置 `DATABASE_URL`：

```bash
DATABASE_URL=postgresql://rhizonp:rhizonp_dev@localhost:5432/rhizonp alembic upgrade head
```

仅用于本地开发的快速建表入口：

```bash
make bootstrap-db
```

导入 synthetic Phase 1 demo fixture：

```bash
make load-demo-fixtures
```

数据模型说明见 `docs/DATA_MODEL.md`。

---

## 4. 常见问题

1. **为什么有两个 `input.csv`？**  
   - `data/input.csv` 是**原始文件**，由用户放置或生成；  
   - `data/faiss_all_acge/files/input.csv` 是**被脚本拷贝过去的文件**，用于追踪已导入索引的文件列表；  
   - 真正用于相似度搜索的是 `index.faiss`、`index.pkl` 等二进制或序列化文件。

2. **向量库在何处？**  
   - `data/faiss_all_acge/index.faiss` 和 `data/faiss_all_acge/index.pkl`。  
   - 只要脚本或系统能正确加载这两个文件，就能进行相似度检索。

3. **模型下载失败或速度慢**  
   - 如果下载失败或速度过慢，可手动下载模型后放到 `~/.cache/modelscope/hub/...` 下对应的目录。  
   - 若你有镜像源或代理，可以在 `rhizonp.config` 或系统网络设置中配置。

4. **数据库连接出错**  
   - 请确保数据库（如 PostgreSQL）已启动，并在 `.env` 或 `rhizonp.config` 中的连接参数正确。

5. **依赖冲突**  
   - 修改 `requirements.txt` 中的版本或单独安装特定版本的包，例如：  
     ```bash
     pip install langchain==0.0.XX
     ```

---

## 5. 总结

- 本项目演示了一个从**文本数据**到**向量检索**再到**数据库查询**与**LLM 分析**的完整流程。  
- 读者可根据自身需求进行个性化扩展，比如换用其他 Embedding 模型、改用不同数据库、添加更多数据过滤逻辑等。

如有更多问题，欢迎在 Issue 进行反馈或进行个性化定制。
