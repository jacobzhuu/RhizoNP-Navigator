# RhizoNP Navigator — Full Plan Implementation Matrix

**Primary specification:** `RHIZONP_NAVIGATOR_MIGRATION_PLAN.md` (v1.0)  
**Last updated:** 2026-07-05 (loop iteration 6 — retrieval-grounded writer + score discipline correction)  
**Repository baseline:** `main` @ Phase 5.2 + NPAtlas bounded adapter

## Status legend

| Status | Meaning |
|---|---|
| FULLY_IMPLEMENTED | Meets plan intent with code + tests |
| IMPLEMENTED_MVP | Runnable but narrower than full plan |
| INTERFACE_ONLY | Protocol/adapter without production validation |
| SYNTHETIC_FIXTURE_ONLY | Deterministic local fixtures only |
| IMPLEMENTED_NOT_VALIDATED | Code exists; no credible empirical proof |
| BLOCKED_BY_EXTERNAL_INPUT | Requires human labels, private data, or credentials |
| DOCUMENTED_ONLY | Described in docs only |
| NOT_STARTED | No meaningful implementation |
| DEFERRED_BY_PLAN | Explicitly deferred in migration plan v1 |

## Completion scores (2026-07-05)

| Lens | Conservative | Point | Optimistic |
|---|---:|---:|---:|
| MVP Engineering | 81% | **84%** | 86% |
| Full Plan Functional | 60% | **67%** | 70% |
| Empirical / Scientific Validation | 18% | **27%** | 32% |

Scoring uses 72 requirements below with equal weight unless noted. **Empirical validation excludes** unit tests, integration traces, bounded cache fetches, and source-provenance wiring unless they involve human judgments, real applicant omics, expert adjudication, or labeled benchmark evaluation. Iteration 5 incorrectly bumped empirical score; corrected here.

---

## Phase 0 — Engineering baseline

| ID | Plan Section | Requirement | Current Status | Evidence | Missing Work | Priority | Blocker |
|---|---|---|---|---|---|---|---|
| E01 | §3 P0-1 | Remove committed secrets | FULLY_IMPLEMENTED | `.env.example`, `check_no_secrets`, CI | Git history purge external | P2 | External rotation |
| E02 | §3 P0-1 | Git history credential purge | NOT_STARTED | `task_plan.md` open item | filter-repo + rotation proof | P2 | External |
| E03 | §19.1 | pydantic-settings config | FULLY_IMPLEMENTED | `config.py` | YAML config files from plan | P3 | — |
| E04 | §3 P0-4 | Cross-platform paths | FULLY_IMPLEMENTED | `pathlib`, CI matrix | Legacy wrapper paths | P3 | — |
| E05 | §3 P0-2 | Reranker wrapper (FlagReranker) | FULLY_IMPLEMENTED | `get_answer.py`, tests | Literature defaults lexical | P3 | — |
| E06 | §3 P0-3 | Multi-chunk FAISS delete | FULLY_IMPLEMENTED | `make_vector_db.py`, tests | — | — | — |
| E07 | §3 P0-6 | pyproject + slim deps | IMPLEMENTED_MVP | `pyproject.toml` | Minimal lockfile | P3 | — |
| E08 | §19.4 | CI ruff/mypy/pytest/secret scan | FULLY_IMPLEMENTED | `.github/workflows/ci.yml` | Full ML stack in CI | P3 | — |
| E09 | §19.2 | Docker postgres + app | IMPLEMENTED_MVP | `docker-compose.yml` | Production API container | P2 | Docker optional |
| E10 | §19.3 | Makefile targets | FULLY_IMPLEMENTED | `Makefile` incl. NPAtlas fetch | Unified CLI names | P3 | — |
| E11 | §3 P0-7 | PROVENANCE + SECURITY docs | FULLY_IMPLEMENTED | `docs/PROVENANCE.md`, `SECURITY.md` | Phase 2–8 provenance updates | P3 | — |
| E12 | §3.1 | Legacy RAGNavigator preserved | FULLY_IMPLEMENTED | Legacy wrappers | Parallel literature stack | P3 | — |

## Phase 1 — Domain model

| ID | Plan Section | Requirement | Current Status | Evidence | Missing Work | Priority | Blocker |
|---|---|---|---|---|---|---|---|
| D01 | §6–7 | Core ORM entities | FULLY_IMPLEMENTED | `domain/models.py`, migration 0001 | — | — | — |
| D02 | §7 | paper_chunks + retrieval provenance | FULLY_IMPLEMENTED | migration 0002 | — | — | — |
| D03 | §7.1 | Full planned table set | NOT_STARTED | Missing synonym/bioactivity/answer tables | 6+ tables | P2 | Design |
| D04 | §7 | Alembic migrations | FULLY_IMPLEMENTED | 2 revisions | More migrations needed | P3 | — |
| D05 | §7 | Repository layer | FULLY_IMPLEMENTED | `storage/repositories.py` | — | — | — |
| D06 | §Phase 1 | Fixture import to PostgreSQL | IMPLEMENTED_MVP | load scripts | Own-data not persisted | P2 | — |
| D07 | §16 | Read/query API | IMPLEMENTED_MVP | `api/app.py` | Full POST surface | P3 | — |

## Phase 2 — Literature retrieval

| ID | Plan Section | Requirement | Current Status | Evidence | Missing Work | Priority | Blocker |
|---|---|---|---|---|---|---|---|
| R01 | §9.2 | SourceAdapter + synthetic adapter | FULLY_IMPLEMENTED | `literature/adapters.py` | — | — | — |
| R02 | §9.2 | PubMed/NCBI adapter | IMPLEMENTED_MVP | `pubmed_adapter.py`, bounded corpus | Metadata-only; not PubMed-wide | P1 | — |
| R03 | §9.2 | Crossref / OpenAlex | NOT_STARTED | Documented out of scope | Adapters | P3 | — |
| R04 | §12 | Structured chunking | FULLY_IMPLEMENTED | `literature/chunking.py` | Full-text sections rare | P3 | — |
| R05 | §11.2 | BM25 | FULLY_IMPLEMENTED | `literature/retrieval.py` | — | — | — |
| R06 | §11.1 | Dense retrieval | IMPLEMENTED_MVP | Hashing default | Production HF default | P1 | — |
| R07 | §11.3 | Hybrid fusion | FULLY_IMPLEMENTED | hybrid modes | — | — | — |
| R08 | §11.4 | Reranker adapters | IMPLEMENTED_MVP | lexical/BGE optional | Real benchmark validation | P1 | Human labels |
| R09 | §11.5 | Metadata filters | FULLY_IMPLEMENTED | `SearchFilters` | — | — | — |
| R10 | §11 | FAISS persistence | IMPLEMENTED_MVP | optional FAISS index | CI skips FAISS | P2 | faiss-cpu |
| R11 | §11 | Model-backed embeddings | INTERFACE_ONLY | HF provider optional | Empirical eval | P1 | Human labels |
| R12 | §Phase 2 DoD | chunk→paper→DOI trace | FULLY_IMPLEMENTED | API trace, tests | — | — | — |
| R13 | §9.2 | Full-text / PDF ingestion | NOT_STARTED | metadata_only corpus | Licensed full text | P3 | Licensing |
| R14 | §9.2 | Production-scale indexing | NOT_STARTED | 149-paper bounded snapshot | PubMed-wide | P3 | — |
| R15 | §17.1 | 100-query benchmark | NOT_STARTED | 3 synthetic + 18 real templates | Expand to 100 | P1 | — |
| R16 | §17.2 | Human relevance labels | BLOCKED_BY_EXTERNAL_INPUT | 18 queries; ~543 pooled candidates; blind export/QC/qrels workflow functional; **0 labels imported** | Complete blind review | **P0** | Human reviewers |
| R17 | §17.3 | R@k, MRR, nDCG | FULLY_IMPLEMENTED | `retrieval_metrics.py` | Real labeled reports | P1 | R16 |
| R18 | §17.4 | Retrieval ablation matrix | IMPLEMENTED_MVP | partial multi-system | Full plan matrix + structured DB arm | P1 | R16 |
| R19 | §18.3 | Adapter contract tests | NOT_STARTED | PubMed unit tests only | timeout/rate-limit suite | P2 | — |

## Phase 3 — Taxonomy-aware evidence

| ID | Plan Section | Requirement | Current Status | Evidence | Missing Work | Priority | Blocker |
|---|---|---|---|---|---|---|---|
| T01 | §13.1 | Taxonomy normalization | IMPLEMENTED_MVP | `AUTO` default; bounded NCBI cache (6 taxa); explicit resolution metadata | Full NCBI coverage; production mirror | P1 | — |
| T02 | §13.1 | Strain/species/genus parsing | IMPLEMENTED_MVP | NormalizedTaxon + fixture strain labels; NCBI species/genus ranks | Strain labels absent from NCBI cache | P2 | — |
| T03 | §13.2 | Rank-aware distance | FULLY_IMPLEMENTED | `taxonomy/distance.py` | — | — | — |
| T04 | §8.1 | Evidence tier A–D | FULLY_IMPLEMENTED | `taxonomy/policy.py` | Standalone policy doc | P3 | — |
| T05 | §13.1 | External taxonomy IDs | IMPLEMENTED_MVP | Real `ncbi_taxid` + lineage in bounded cache; AUTO/API/pipeline wired | Universal resolver; live fetch default | P1 | — |
| T06 | §13.1 | Synonym resolution (production) | IMPLEMENTED_MVP | NCBI cache synonym lookup (e.g. Chainia→1883) + fixture aliases | DB synonym tables | P2 | — |
| T07 | §10.3 | UNRESOLVED handling | FULLY_IMPLEMENTED | normalization + linking | — | — | — |
| T08 | §18.4 | Scientific safety tests | FULLY_IMPLEMENTED | taxonomy/writer tests | Broader case set | P2 | — |
| T09 | §8 | docs/EVIDENCE_POLICY.md | NOT_STARTED | Policy in code/tests | Standalone doc | P3 | — |

## Phase 4 — Natural products

| ID | Plan Section | Requirement | Current Status | Evidence | Missing Work | Priority | Blocker |
|---|---|---|---|---|---|---|---|
| N01 | §Phase 4 | Candidate linking engine | IMPLEMENTED_MVP | `candidate_engine.py`; default `record_source=auto` | Full NP corpus scale | P1 | — |
| N02 | §9.3 | NPAtlas integration | IMPLEMENTED_MVP | AUTO main path + API; 12-record bounded snapshot; real NPAID/URL provenance | Bioactivity fields; scale beyond bounded snapshot | P1 | CC-BY-NC scope |
| N03 | §9.3 | MIBiG adapter (interface) | NOT_STARTED | Plan defers full integration | Stub `MibigAdapter` | P3 | DEFERRED_BY_PLAN |
| N04 | §13.3 | Compound normalization | IMPLEMENTED_MVP | alias file + InChIKey in NPAtlas records | Structure search | P2 | — |
| N05 | §7 | Bioactivity DB records | SYNTHETIC_FIXTURE_ONLY | fixture JSON fields | `bioactivities` table | P2 | — |
| N06 | §Phase 4 | Producer taxon + provenance | IMPLEMENTED_MVP | NPAtlas snapshot has DOI/PMID/NPAID URLs | DB-backed NP records | P1 | — |
| N07 | §14.5 | Linker-level conflict engine | IMPLEMENTED_MVP | Writer conflict only | Evidence linker conflicts | P2 | — |

## Phase 5 — Own-data-to-literature

| ID | Plan Section | Requirement | Current Status | Evidence | Missing Work | Priority | Blocker |
|---|---|---|---|---|---|---|---|
| O01 | §10.1 | CSV schemas | FULLY_IMPLEMENTED | `omics/csv_ingestion.py` | — | — | — |
| O02 | §10.2 | Raw label preservation | FULLY_IMPLEMENTED | AssociationRecord | — | — | — |
| O03 | §10.3 | Resolution status visible | IMPLEMENTED_MVP | grading output | DB persistence | P2 | O07 |
| O04 | §10 | 16S observations (real) | BLOCKED_BY_EXTERNAL_INPUT | demo fixture only | De-sensitized real 16S | P1 | Applicant data |
| O05 | §10 | LC-MS observations (real) | BLOCKED_BY_EXTERNAL_INPUT | demo fixture only | Real LC-MS validation | P1 | Applicant data |
| O06 | §8.2 | Chemical ID tier policy | IMPLEMENTED_MVP | C4 limitations in pipeline | Full C1–C4 enforcement | P2 | — |
| O07 | §10.2 | Association DB persistence | IMPLEMENTED_NOT_VALIDATED | `omics/persistence.py` opt-in; **validated on SQLite in-memory tests only** | PostgreSQL integration (V11); API flag | P1 | Docker daemon |
| O08 | §10 / Phase 5 | Own-data → literature search | IMPLEMENTED_MVP | `literature_bridge.py`, `search_paper_chunks`, Phase 5.2 validation | Default disabled; not PubMed-wide quality eval | P1 | R16 for quality |
| O09 | §10.4 | Candidate matrix + paper counts | IMPLEMENTED_MVP | CSV has literature_status/hit_count | Richer paper-level matrix | P2 | — |
| O10 | §10.4 | Validation suggestions | IMPLEMENTED_MVP | limitations lists | Evidence-driven from papers | P2 | — |
| O11 | §9.1 | Real applicant omics validation | BLOCKED_BY_EXTERNAL_INPUT | synthetic demo only | Private data path | P1 | Applicant data |

## Phase 6 — Grounded writer

| ID | Plan Section | Requirement | Current Status | Evidence | Missing Work | Priority | Blocker |
|---|---|---|---|---|---|---|---|
| W01 | §15.2 | Pydantic answer schema | FULLY_IMPLEMENTED | `writer/models.py` | — | — | — |
| W02 | §15 | Deterministic fallback writer | FULLY_IMPLEMENTED | `fallback_writer.py` | — | — | — |
| W03 | §15 | LLM grounded writer | INTERFACE_ONLY | `writer/service.py` disabled | Constrained LLM path | P1 | API keys + eval |
| W04 | §14 | Scientific constraint validator | IMPLEMENTED_MVP | taxonomy + writer logic | Unified evidence module | P2 | — |
| W05 | §15.2 | Claim-level citations | IMPLEMENTED_MVP | retrieval-grounded writer + structural citation validation | Human faithfulness adjudication | P1 | V02 |
| W06 | §14.5 | Conflict detection | IMPLEMENTED_MVP | explicit predicate conflict rule (`PRODUCES` vs `DOES_NOT_PRODUCE`) | Literature-derived semantic conflicts | P2 | — |
| W07 | §20 | Audit view UI | IMPLEMENTED_MVP | `GroundedReport.tsx` (WIP uncommitted) | E2E browser validation | P3 | — |
| W08 | §17.5 | Hallucination control (evaluated) | IMPLEMENTED_NOT_VALIDATED | structural validity + heuristic diagnostics only | Human faithfulness eval | P1 | V02 |

## Phase 7 — Evaluation

| ID | Plan Section | Requirement | Current Status | Evidence | Missing Work | Priority | Blocker |
|---|---|---|---|---|---|---|---|
| V01 | §17.1 | 100-query benchmark | NOT_STARTED | 21 queries defined; **deferred until R16 labels exist** | Expand after labeling | P2 | R16 |
| V02 | §17.2 | Human relevance labels | BLOCKED_BY_EXTERNAL_INPUT | full annotation workflow (`annotation.py`, blind sheet, QC, qrels, judged@k) | Import labels only | **P0** | Human reviewers |
| V03 | §17.3 | Retrieval metrics | FULLY_IMPLEMENTED | metric code | Labeled benchmark reports | P1 | V02 |
| V04 | §17.4 | Multi-system comparison | IMPLEMENTED_MVP | synthetic gold runs | Real labeled comparison | P1 | V02 |
| V05 | §17.4 | Ablation report artifacts | IMPLEMENTED_MVP | JSON reports | Plan CSV/MD paths | P2 | V02 |
| V06 | §17.5 | Citation precision | IMPLEMENTED_NOT_VALIDATED | structural `citation_ref_validity_rate` harness | Human adjudication | P1 | V02 |
| V07 | §17.5 | Citation coverage | IMPLEMENTED_MVP | provenance/trace completeness metrics | Scaled labeled eval | P2 | V02 |
| V08 | §17.5 | Faithfulness metric | IMPLEMENTED_NOT_VALIDATED | heuristic overlap diagnostic only (`human_faithfulness_pending`) | Human faithfulness labels | P1 | V02 |
| V09 | §17.5 | Abstention accuracy | IMPLEMENTED_NOT_VALIDATED | writer regression + metrics hook | Must-abstain benchmark set | P1 | — |
| V10 | §17.5 | Taxonomy safety accuracy | IMPLEMENTED_NOT_VALIDATED | 2 replay cases | Real query eval | P1 | V02 |
| V11 | §18.2 | PG integration test chain | NOT_STARTED | SQLite unit tests only; **Docker unavailable in loop env** | Docker PG E2E per Option A checklist | P1 | Docker daemon |
| V12 | §Phase 7 | Eval reports directory | FULLY_IMPLEMENTED | `data/eval/reports/latest/` | — | — | — |

## Phase 8 — Demo & delivery

| ID | Plan Section | Requirement | Current Status | Evidence | Missing Work | Priority | Blocker |
|---|---|---|---|---|---|---|---|
| P01 | §16 | POST search API | FULLY_IMPLEMENTED | `/api/v1/search` | — | — | — |
| P02 | §16 | POST evidence/query | NOT_STARTED | `/taxonomy/grade` instead | Plan-shaped endpoint | P3 | — |
| P03 | §16 | Multipart omics upload | NOT_STARTED | JSON path only | File upload API | P3 | — |
| P04 | §16 | Candidate link API | IMPLEMENTED_MVP | `/natural-products/link` | Path rename | P3 | — |
| P05 | §16 | Grounded answer API | IMPLEMENTED_MVP | `/writer/answer` + optional `retrieve_evidence` | Path rename | P3 | — |
| P06 | §5 | Unified CLI module | IMPLEMENTED_MVP | `scripts/*.py` | `rhizonp.cli` | P3 | — |
| P07 | §20 | Four demo UI pages | IMPLEMENTED_MVP | 6 React pages | Commit stable frontend | P2 | WIP files |
| P08 | §Phase 8 | One-command demo/smoke | FULLY_IMPLEMENTED | `make smoke`, `make demo` | — | — | — |
| P09 | §22 | Three case studies | FULLY_IMPLEMENTED | demo outputs | Honest eval numbers | P3 | V02 |
| P10 | §19 | Fresh-machine reproducibility | IMPLEMENTED_NOT_VALIDATED | offline fixtures | Docker PG E2E proof | P2 | Docker |

---

## Top remaining gaps (re-ranked after iteration 6)

1. **Human-labeled real retrieval benchmark** (R16, V02) — BLOCKED_BY_EXTERNAL_INPUT (workflow ready; labels absent)  
2. **PostgreSQL full-stack validation** (V11, O07, P10) — **blocked: Docker daemon unavailable locally**  
3. **Real applicant omics validation** (O04, O05, O11) — BLOCKED_BY_EXTERNAL_INPUT  
4. **Human citation faithfulness adjudication** (W08, V08) — heuristic diagnostics only  
5. **Evaluated LLM writer** (W03) — disabled placeholder  
6. **NPAtlas scale + bioactivity** (N02, N05) — bounded 12-record corpus  
7. **Full taxonomy coverage** (T01, T05) — bounded 6-taxa cache  
8. **MIBiG adapter stub** — **deferred; do not prioritize interface-only checkbox**

## Iteration log

| Iteration | Gap addressed | Score delta (functional / empirical) |
|---|---|---|
| 0 | Baseline audit + matrix creation | 60% / 26% |
| 1 | NPAtlas bounded adapter + snapshot | 60% / 26% |
| 2 | Own-data DB persistence (SQLite-tested) | 61% / 26% |
| 3 | NCBI Taxonomy bounded resolver + cache | 62% / 27% |
| 4 | NPAtlas AUTO on own-data/API main path | 63% / 27% |
| 5 | NCBI bounded taxonomy AUTO authority | 65% / **27%** (empirical held; iter 5 +2 error corrected) |
| 6 | Retrieval-grounded writer + citation validity harness | **67%** / **27%** (real bounded trace; no human faithfulness) |

---

*This matrix is the live source of truth for loop prioritization. Update after each vertical slice.*
