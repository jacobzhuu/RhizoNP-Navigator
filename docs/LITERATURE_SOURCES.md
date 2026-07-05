# Literature Source Adapter Policy

Phase 2 defines source adapter boundaries for literature ingestion. **PubMed/NCBI E-utilities metadata fetch is implemented.** Crossref, OpenAlex, Europe PMC, and licensed full-text ingestion are **not implemented**.

## Implemented Today

- `SourceAdapter` protocol in `rhizonp.literature.adapters`
- `SyntheticLiteratureAdapter` for fixture-backed local development and tests
- `PubMedEutilitiesAdapter` for metadata-only PubMed title/abstract fetch via NCBI E-utilities
- Injectable HTTP client (`rhizonp.literature.http_client`) so unit tests never require live network calls
- Structured chunking and provenance fields on normalized records
- Bounded domain corpus workflow (`scripts/build_domain_corpus.py`)
- Offline Phase 2 retrieval benchmark framework (`scripts/run_retrieval_eval.py`)

## Adapter Contract

Every source adapter must implement:

```python
class SourceAdapter(Protocol):
    source_name: str

    def fetch(self, query: dict) -> list[RawLiteratureRecord]: ...
    def normalize(self, record: RawLiteratureRecord) -> NormalizedLiteratureRecord: ...
    def provenance(self, record: RawLiteratureRecord) -> dict: ...
```

Design requirements:

1. **Explicit provenance** — every fetched record must record source name, fetch timestamp, query parameters, and API policy reference.
2. **Isolated network I/O** — HTTP clients must be injectable so unit tests never require live network calls.
3. **Rate-limit awareness** — adapters must expose configured request limits; callers must not hard-code credentials.
4. **No fake integration claims** — README/docs must not say a source is integrated until fetch + normalize + tests exist.
5. **License-first** — full text and metadata reuse must be checked against source terms before ingestion pipelines are enabled.

## PubMed / NCBI E-utilities

Implemented scope:

- `esearch` PMID lookup from a PubMed query term
- `efetch` XML metadata parse for title, abstract, journal, year, DOI, PMCID, PMID
- Conservative mapping into existing `Paper` schema through `ingest_literature_records`
- Metadata-only ingestion (`metadata_only=true`, `full_text=false`)

Not implemented:

- Full-text download
- PDF OCR
- Bulk offline mirror beyond bounded configured corpus snapshots

Configuration (see `.env.example`):

- `NCBI_TOOL_NAME`
- `NCBI_EMAIL` (recommended by NCBI policy)
- `NCBI_API_KEY` (optional)
- `NCBI_REQUEST_TIMEOUT`
- `NCBI_MAX_RESULTS`

Policy reference: [NCBI website and data usage policies](https://www.ncbi.nlm.nih.gov/home/about/policies/)

## Candidate External Sources (Not Implemented)

| Source | Primary use | Status |
| --- | --- | --- |
| Crossref REST API | DOI metadata | Not implemented |
| OpenAlex | Scholarly metadata graph | Not implemented |
| Licensed OA full text | Section-aware chunking | Not implemented |

## Domain Corpus Workflow

`data/eval/domain_corpus_queries.json` defines bounded PubMed queries for:

- plant–microbe interactions
- rhizosphere microbiome
- PGPR / Streptomyces / biocontrol
- microbial natural products / secondary metabolites
- bridge questions (metabolites ↔ plant–microbe)

Versioned snapshots live under `data/snapshots/pubmed/<corpus_id>/` with `corpus.json` and `manifest.json` (checksums, deduplication rules, query config provenance).

Commands:

```bash
make fetch-domain-corpus   # live network; writes data/snapshots/pubmed/rhizonp_domain_v1/
make ingest-domain-corpus  # offline ingest from saved snapshot
```

Fetch and ingest are intentionally separatable so evaluation can run offline after a snapshot exists.

## Retrieval Benchmark

### Synthetic fixture benchmark (CI default)

`data/eval/phase2_retrieval_gold.json` provides explicit gold labels for a **small synthetic mini-benchmark**. It is not a production benchmark.

```bash
make eval-retrieval
```

If `DATABASE_URL` is not configured, this command automatically uses an in-memory SQLite
database for the offline synthetic benchmark. Generated reports are written under
`data/eval/reports/latest/`.

### Real PubMed benchmark (human labels required)

`data/eval/phase2_real_pubmed_benchmark.json` defines 18 paper-level domain queries with graded relevance schema (0/1/2). **No fabricated gold labels** — annotation is pending until human review.

```bash
make export-annotation-candidates                              # export CSV for review
make import-annotation-labels REVIEW=path/to/reviewed.csv      # import 0/1/2 labels
make eval-real-retrieval                                       # offline eval after labels
```

See `docs/PHASE2_CLOSURE_AUDIT.md` for Phase 2 engineering vs empirical DoD status.

Supported offline systems by default:

- BM25
- deterministic/hash dense
- hybrid (hash)
- hybrid + lexical rerank

Optional systems when dependencies/models are explicitly enabled:

- model-backed dense/hybrid
- hybrid + BGE reranker

Metrics: Recall@5, Recall@10, MRR@10, nDCG@10.

## Non-Goals for Phase 2

- Autonomous agent fetching
- Bulk corpus mirroring beyond bounded configured fetches
- PDF OCR pipelines
- Claiming benchmark-quality retrieval without explicit gold labels
- Taxonomy-aware evidence grading (Phase 3)
