# Literature Provenance Baseline

Phase 2 currently provides a local, synthetic, test-backed provenance baseline for literature retrieval. It does not integrate real PubMed, Crossref, OpenAlex, Europe PMC, PDF full text, or licensed corpora.

## Implemented

- `paper_chunks` table with structured section, paragraph, character span, source hash, and metadata.
- `retrieval_runs` and `retrieval_results` tables for persisted search provenance.
- `SourceAdapter` protocol and `SyntheticLiteratureAdapter` fixture adapter.
- Structured chunking for title, abstract, methods, results, discussion, and additional sections.
- Local BM25 lexical search over persisted `paper_chunks`.
- `POST /api/v1/search` returning traceable results.

Each search result is traceable through:

```text
retrieval_result -> paper_chunk -> paper -> DOI/source URL
```

## Not Implemented Yet

- Real external literature adapters.
- Dense vector retrieval over literature chunks.
- Hybrid dense + BM25 fusion.
- Reranker integration for literature results.
- License-aware full-text download.
- Taxonomy-aware evidence grading, which belongs to Phase 3.

## Fixture Boundary

`data/fixtures/phase2_literature_demo.json` is synthetic. It is not real literature, not real experimental evidence, and not a claim that any taxon produces any compound.
