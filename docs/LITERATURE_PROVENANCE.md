# Literature Provenance Baseline

Phase 2 provides a local, synthetic, test-backed provenance baseline for literature retrieval. Real PubMed, Crossref, OpenAlex, Europe PMC, PDF full text, and licensed corpora are **not integrated**.

See also: [LITERATURE_SOURCES.md](./LITERATURE_SOURCES.md)

## Implemented

- `paper_chunks` table with structured section, paragraph, character span, source hash, and metadata.
- `retrieval_runs` and `retrieval_results` tables for persisted search provenance.
- `SourceAdapter` protocol and `SyntheticLiteratureAdapter` fixture adapter.
- Structured chunking for title, abstract, methods, results, discussion, and additional sections.
- Local BM25 lexical search over persisted `paper_chunks`.
- Literature embedding adapter boundary:
  - `hashing` deterministic provider for offline tests
  - optional `huggingface` provider with injectable embedder factory
- `LiteratureVectorIndex` protocol with:
  - JSON-serializable `InMemoryLiteratureVectorIndex`
  - optional `FaissLiteratureVectorIndex` when `faiss-cpu` is installed
- Hybrid BM25 + dense fusion with configurable weights.
- Literature reranker adapter boundary:
  - `none`, `lexical`, and optional `bge` providers
  - factory-based explicit selection via settings
- `POST /api/v1/search` returning traceable results.

Each search result is traceable through:

```text
retrieval_result -> paper_chunk -> paper -> DOI/source URL
```

## Not Implemented Yet

- Real external literature adapters (PubMed/Crossref/OpenAlex/full text).
- License-aware full-text download pipelines.
- Production embedding/reranker quality benchmarks.
- Taxonomy-aware evidence grading, which belongs to Phase 3.

## Search Modes

`POST /api/v1/search` supports:

- `bm25`: local lexical retrieval.
- `dense`: embedding-backed retrieval through the literature vector index boundary. Defaults to deterministic hashing embeddings for reproducible tests.
- `hybrid`: weighted BM25 + dense fusion through the same vector index boundary.
- `hybrid_rerank`: hybrid retrieval followed by the configured literature reranker (default: lexical overlap).

These modes are intentionally deterministic in the default test configuration. They are not benchmarks and do not claim model-level semantic retrieval quality unless explicit model-backed providers are configured.

## Adapter Settings

Phase 2 literature adapters are configured through environment variables (see `.env.example`):

| Setting | Default | Purpose |
| --- | --- | --- |
| `LITERATURE_EMBEDDING_PROVIDER` | `hashing` | `hashing` or `huggingface` |
| `LITERATURE_HASHING_DIMENSIONS` | `128` | Deterministic test embedding size |
| `LITERATURE_VECTOR_INDEX_BACKEND` | `in_memory` | `in_memory` or `faiss` |
| `LITERATURE_RERANKER` | `lexical` | `none`, `lexical`, or `bge` |

Model IDs remain separate (`EMBEDDING_MODEL`, `RERANKER_MODEL`) and must be explicit when selecting model-backed providers.

## Vector Index Boundary

`InMemoryLiteratureVectorIndex` and optional `FaissLiteratureVectorIndex` can be built from persisted `PaperChunk` rows, searched with an embedding provider, and saved/loaded via `pathlib`. Dense and hybrid retrieval accept an optional `LiteratureVectorIndex`, so adapters can be swapped without changing API result provenance.

The local index stores chunk IDs, paper IDs, text, embedding vectors, and trace metadata such as section, source hash, DOI, and source URL.

## Metadata Filters

Search filters are split by storage surface:

- Column-backed filters are applied in the SQLAlchemy query: `year_from`, `year_to`, `sections`, `dois`, `source_urls`, and `journals`.
- Metadata-backed filters are applied after fetch for cross-database compatibility: `source_types`, `taxa`, `compounds`, and `host`.

The metadata-backed filters avoid PostgreSQL-only JSONB operators so the same unit tests run on SQLite, macOS, Linux, and Windows.

## Fixture Boundary

`data/fixtures/phase2_literature_demo.json` is synthetic. It is not real literature, not real experimental evidence, and not a claim that any taxon produces any compound.
