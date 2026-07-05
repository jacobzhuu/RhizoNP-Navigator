# Architecture Overview

RhizoNP Navigator is organized as a staged evidence pipeline rather than a single RAG chatbot.

```text
Own omics CSV / demo fixtures
        │
        ▼
Taxonomy normalization + evidence grading (Phase 3)
        │
        ▼
Natural product candidate linking (Phase 4)
        │
        ├──────────────┐
        ▼              ▼
Literature retrieval   Structured NP fixtures
(Phase 2)              (Phase 4)
        │              │
        └──────┬───────┘
               ▼
Evidence-grounded writer (Phase 6)
               │
               ▼
Evaluation + demo package (Phase 7/8)
```

## Core packages

| Package | Responsibility |
|---|---|
| `rhizonp.domain` | SQLAlchemy schema |
| `rhizonp.literature` | Chunking, retrieval, provenance |
| `rhizonp.taxonomy` | Normalization, distance, evidence tier policy |
| `rhizonp.linking` | Natural product candidate matrix |
| `rhizonp.omics` | Own-data CSV ingestion and pipeline |
| `rhizonp.writer` | Deterministic grounded answer synthesis |
| `rhizonp.evaluation` | Retrieval and end-to-end metrics |
| `rhizonp.demo` | Offline smoke/demo runner |
| `rhizonp.api` | FastAPI integration layer |

## Design principles

- Taxonomy-aware evidence grading prevents genus-level 16S observations from becoming strain-level production claims.
- Every answer binds claims to evidence references or abstains.
- External integrations are optional; offline fixtures support reproducible demos and tests.
- Metrics are reported honestly from deterministic replay cases, not fabricated benchmark gains.
