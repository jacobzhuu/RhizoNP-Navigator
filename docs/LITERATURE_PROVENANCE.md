# Literature Provenance Baseline

Phase 2 currently provides a local, synthetic, test-backed provenance baseline for literature retrieval. It does not integrate real PubMed, Crossref, OpenAlex, Europe PMC, PDF full text, or licensed corpora.

## Implemented

- `paper_chunks` table with structured section, paragraph, character span, source hash, and metadata.
- `retrieval_runs` and `retrieval_results` tables for persisted search provenance.
- `SourceAdapter` protocol and `SyntheticLiteratureAdapter` fixture adapter.
- Structured chunking for title, abstract, methods, results, discussion, and additional sections.
- Local BM25 lexical search over persisted `paper_chunks`.
- Deterministic hashing-vector dense retrieval baseline.
- `LiteratureVectorIndex` protocol with a JSON-serializable `InMemoryLiteratureVectorIndex` baseline.
- Hybrid BM25 + dense fusion with configurable weights.
- Local lexical-overlap reranker through the same `score(query, passages)` protocol shape used by the existing reranker adapter.
- `POST /api/v1/search` returning traceable results.

Each search result is traceable through:

```text
retrieval_result -> paper_chunk -> paper -> DOI/source URL
```

## Not Implemented Yet

- Real external literature adapters.
- Production model-backed literature embeddings.
- FAISS-backed literature vector index adapter.
- External cross-encoder or BGE reranker integration for literature results.
- License-aware full-text download.
- Taxonomy-aware evidence grading, which belongs to Phase 3.

## Search Modes

`POST /api/v1/search` supports:

- `bm25`: local lexical retrieval.
- `dense`: deterministic hashing-vector retrieval through the local vector index boundary, intended for reproducible tests and interface validation.
- `hybrid`: weighted BM25 + deterministic dense fusion through the same vector index boundary.
- `hybrid_rerank`: hybrid retrieval followed by local lexical-overlap reranking.

These modes are intentionally deterministic. They are not benchmarks and do not claim model-level semantic retrieval quality.

## Vector Index Boundary

`InMemoryLiteratureVectorIndex` can be built from persisted `PaperChunk` rows, searched with an embedding provider, and saved/loaded as JSON via `pathlib`. Dense and hybrid retrieval accept an optional `LiteratureVectorIndex`, so a future FAISS/model-backed adapter can replace the local implementation without changing API result provenance.

The local index stores chunk IDs, paper IDs, text, embedding vectors, and trace metadata such as section, source hash, DOI, and source URL. It is a deterministic development and test baseline, not a production semantic search index.

## Metadata Filters

Search filters are split by storage surface:

- Column-backed filters are applied in the SQLAlchemy query: `year_from`, `year_to`, `sections`, `dois`, `source_urls`, and `journals`.
- Metadata-backed filters are applied after fetch for cross-database compatibility: `source_types`, `taxa`, `compounds`, and `host`.

The metadata-backed filters avoid PostgreSQL-only JSONB operators so the same unit tests run on SQLite, macOS, Linux, and Windows.

## Fixture Boundary

`data/fixtures/phase2_literature_demo.json` is synthetic. It is not real literature, not real experimental evidence, and not a claim that any taxon produces any compound.
