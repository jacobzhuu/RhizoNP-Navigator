# Phase 2R: Quantified Retrieval Baseline Roadmap

**Goal:** Turn the 149-paper abstract-level demo corpus into a **scaled, human-labeled, quantifiable** research retrieval system. Only after error analysis, decide whether to add **PMC OA JATS/XML full text** for a subset.

**Explicit non-goal (for now):** Generic PDF ingestion, OCR, or non-OA full-text pipelines.

---

## Success criteria

| Gate | Target | Evidence artifact |
| --- | --- | --- |
| G1 Scale | ≥500 deduplicated PubMed metadata records | `data/snapshots/pubmed/rhizonp_domain_v2/manifest.json` |
| G2 Labels | ≥18/18 benchmark queries with imported 0/1/2 grades | `phase2_real_pubmed_benchmark.json` `annotation_status: complete` |
| G3 Baseline | Reported R@5, R@10, MRR@10, nDCG@10, Judged@k on real labels | `data/eval/reports/latest/real_pubmed_*.json` |
| G4 Ablation | ≥4 systems compared (bm25, dense, hybrid, hybrid_rerank) | Same report, multi-system table |
| G5 Error analysis | Written failure taxonomy with counts | `findings.md` § Phase 2R error analysis |
| G6 JATS decision | Go / no-go with criteria met | `findings.md` § JATS gate |

---

## Phase sequence

```text
A. Corpus v2 (metadata scale-up)
        ↓
B. Ingest + FAISS rebuild
        ↓
C. Export blind annotation pool (v1 corpus OK for pilot; v2 after ingest)
        ↓
D. Human labeling (external reviewer time)
        ↓
E. Import labels + QC
        ↓
F. Real-benchmark eval + ablation report
        ↓
G. Error analysis (abstract ceiling?)
        ↓
H. JATS pilot (OA subset only) — ONLY if G5 triggers
```

---

## A. Corpus scale-up (v1 → v2)

| Item | v1 | v2 target |
| --- | ---: | ---: |
| Corpus ID | `rhizonp_domain_v1` | `rhizonp_domain_v2` |
| Records | 149 | 500–800 |
| Queries | 17 | 25 |
| `default_retmax` | 12 | 25 |
| `max_total_records` | 200 | 800 |
| Full text | metadata-only | metadata-only (unchanged) |

Config: `data/eval/domain_corpus_queries_v2.json`

Commands:

```bash
make fetch-domain-corpus-v2    # live NCBI; writes snapshot
make ingest-domain-corpus-v2   # offline ingest from snapshot
make build-literature-faiss-index
```

---

## B. Human labeling workflow

1. `make export-annotation-candidates` — pooled top-20 per query, blind CSV
2. Reviewer fills `grade` (0/1/2) per `docs/ANNOTATION_POLICY.md`
3. `make import-annotation-labels REVIEW=path/to/reviewed.csv`
4. Optional: `make report-qc-consistency REVIEW=...`

**Pilot shortcut:** Label 5–10 queries first to unblock ablation tooling before full 18.

---

## C. Baseline evaluation

```bash
make eval-real-retrieval
```

Systems (offline default): `bm25`, `dense_hash`, `hybrid_hash`, `hybrid_rerank_lexical`.

Optional production profile (after labels exist):

```bash
LITERATURE_RETRIEVAL_PROFILE=standard_rag make eval-real-retrieval
```

Report scope: **within-corpus only** (`docs/BENCHMARK_SCOPE.md`).

---

## D. Error analysis template (fill after G3)

For each benchmark query, classify top failures:

| Failure mode | Definition | Full-text might help? |
| --- | --- | --- |
| `PAPER_MISS` | Relevant PMID not in top-10 | Maybe (if not in corpus) |
| `CHUNK_MISS` | Right paper, wrong section/chunk | **Yes** (methods/results) |
| `ENTITY_MISS` | Strain/compound/BGC only in body | **Yes** |
| `SEMANTIC_DRIFT` | Related but off-intent paper ranked high | Unlikely |
| `LEXICAL_GAP` | Query terms absent from abstract | **Yes** |
| `RANK_NOISE` | Correct paper in pool but low rank | Maybe (reranker) |

**JATS gate triggers** (need ≥2 of):

1. ≥30% of grade-2 misses are `CHUNK_MISS` or `ENTITY_MISS`
2. Section filter `results`/`methods` would change ≥20% of grade-2 qrels
3. ≥40% of grade-2 PMIDs have PMC OA full text available
4. Abstract-only Recall@10 plateau across ablation (Δ < 0.05)

**JATS gate blockers** (any one → defer):

- G2 incomplete (<18 labeled queries)
- G3 not run
- OA coverage <25% of grade-2 PMIDs

---

## E. JATS pilot scope (if gate opens)

- Source: Europe PMC / PMC OA XML only
- Adapter: new `EuropePmcJatsAdapter` → populate `record.sections`
- Reuse: existing `structured_chunk_record()` — no new chunking logic
- Corpus: OA subset of v2 only; separate `corpus_revision` bump
- Eval: same 18 queries + labels; ablation `abstract_only` vs `jats_oa`

---

## Loop agent instructions

On each `/loop` tick:

1. Read `task_plan.md`, `progress.md`, `findings.md`, this file.
2. Identify the **first incomplete gate** (G1–G6).
3. Execute the next **automatable** step; record human blockers explicitly.
4. Update `progress.md`; update gate status in `task_plan.md`.
5. Do **not** start JATS/PDF work until G5 error analysis and G6 decision are documented.

---

## Related docs

- `docs/BENCHMARK_SCOPE.md`
- `docs/ANNOTATION_POLICY.md`
- `docs/PHASE2_CLOSURE_AUDIT.md`
- `docs/LITERATURE_SOURCES.md`
- `docs/FULL_PLAN_GAP_AUDIT.md` § Tier 1
