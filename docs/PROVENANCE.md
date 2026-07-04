# Provenance

## Upstream Baseline

This repository currently derives from the earlier RAGNavigator prototype. The preserved baseline capabilities are:

- CSV ingestion through LangChain loaders.
- Recursive text chunking.
- local embedding generation.
- FAISS vector search.
- reranking.
- UUID extraction from retrieved chunks.
- PostgreSQL lookup.
- LLM-assisted filtering and ranking.

## Current Migration Scope

The RhizoNP Navigator migration is being performed incrementally according to `RHIZONP_NAVIGATOR_MIGRATION_PLAN.md`. Phase 0 focuses on security, reproducibility, cross-platform configuration, reranker compatibility, vector-store deletion correctness, dependency hygiene, and tests.

## Contributions Added In This Migration

- Environment-driven settings with no committed runtime secrets.
- Cross-platform path handling based on `pathlib`.
- Lazy embedding initialization to avoid model loading at import time.
- A `RerankerProtocol` plus a `BGEReranker` adapter for `BAAI/bge-reranker-v2-m3` via `FlagReranker`.
- Multi-chunk FAISS deletion by canonical source path.
- Phase 0 unit tests and project tooling configuration.

## Scientific Boundary

Future RhizoNP-specific functionality must not claim unsupported biological conclusions. In particular:

- genus-level 16S evidence must not be presented as strain-level natural-product production;
- unknown LC-MS features must not be presented as confirmed compounds;
- correlation must not be presented as causation;
- insufficient evidence must remain representable as `INSUFFICIENT_EVIDENCE`.

## Notes

Any API keys or database passwords that previously appeared in repository history must be rotated or revoked outside this code change. Removing them from the working tree does not invalidate already exposed credentials.
