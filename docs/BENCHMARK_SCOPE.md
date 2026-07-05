# Phase 2 Real PubMed Benchmark Scope

This document defines the **evaluation scope** for `phase2_real_pubmed_v1`. Results must
be reported within this scope only.

---

## Bounded Domain Corpus

- **Corpus ID:** `rhizonp_domain_v1`
- **Size:** 149 deduplicated PubMed metadata records (metadata-only, no full text)
- **Construction:** 17 bounded PubMed domain queries in `data/eval/domain_corpus_queries.json`
- **Categories covered:** plant–microbe interactions, rhizosphere microbiome,
  PGPR / *Streptomyces* / biocontrol, microbial natural products, metabolite–interaction bridges

This is **not** all of PubMed. It is a deliberately small, domain-focused snapshot.

---

## Within-Corpus Ranking Evaluation

All Phase 2 real-benchmark retrieval metrics are **within-corpus**:

- Retrieval runs over the ingested 149-paper snapshot only.
- Labels apply to PMIDs in that corpus.
- Systems are compared on how they rank **already-ingested** candidate papers.

Do **not** describe results as:

- “PubMed-wide search performance”
- “open-web literature retrieval quality”
- general biomedical search benchmark scores

Acceptable wording:

- “within the RhizoNP Phase 2 bounded domain corpus (n=149)”
- “on 18 domain benchmark queries with human-labeled PMIDs from the snapshot”

---

## Judgment Coverage

Future systems (especially model-backed retrievers) may return PMIDs **outside the
original annotation pool**. Metrics therefore include **Judged@5** and **Judged@10**:
the fraction of top-k retrieved PMIDs that have human labels.

Low Judged@k indicates incomplete label coverage for that system's ranked list.
Do not compare Recall@k across systems with very different Judged@k without noting coverage.

---

## Annotation Pool vs Evaluation Corpus

- **Evaluation corpus:** all 149 snapshot papers (ingested for retrieval index).
- **Annotation pool:** union of multi-system top-k hits per query (typically subset per query).
- Papers never pooled for a query remain unjudged unless manually added.

Unjudged retrieved papers are excluded from qrels (see `docs/ANNOTATION_POLICY.md`).

---

## Writer Safety Benchmark (deterministic regression)

- **Benchmark ID:** `writer_safety_v1`
- **Cases:** 16 static + dynamic fixtures in `data/eval/writer_safety_cases.json` (plus own-data and real bounded PubMed dynamic paths at runtime)
- **Labels:** Built-in expected writer status, forbidden claim patterns, and required limitations — **not human scientific adjudication**
- **Command:** `make eval-writer-safety`

This benchmark evaluates abstention, explicit conflict reporting, bounded candidate-level answers, heuristic overclaim detection, and structural citation validity. It does **not** measure citation faithfulness, production confirmation, or causal inference correctness.

Do **not** describe passing results as:

- human validation of writer faithfulness
- empirical proof of scientific accuracy
- justification for stronger production or causality claims

Acceptable wording:

- “deterministic writer safety/regression benchmark (n=16)”
- “must-abstain and conflict predicates pass offline fixture replay”

---

## NPAtlas Bounded Bioactivity (origin-reference derived)

- **Snapshot:** `data/snapshots/npatlas/rhizonp_domain_v1/` (12 compounds, CC-BY-NC-4.0)
- **Bioactivity source:** conservative keyword extraction from NPAtlas `origin_reference.title` text
- **Command:** `make validate-npatlas-bioactivity`

The NPAtlas compound API does **not** expose structured assay bioactivity records in the current OpenAPI surface. Derived fields are literature-reported metadata only and do **not** affect candidate ranking scores.

Do **not** describe derived bioactivity as:

- assay-validated activity
- empirical proof of compound efficacy
- equivalent to a populated PostgreSQL `bioactivities` table

Acceptable wording:

- “origin-reference-derived bioactivity metadata on bounded NPAtlas snapshot (n=12)”
- “title-keyword extraction with explicit provenance limitations”

---

## Scientific Constraint Consistency (cross-module regression)

- **Benchmark ID:** `scientific_constraint_v1`
- **Scope:** Validates that taxonomy grading, linking, own-data pipeline, literature bridge, and writer outputs obey the same biological/evidentiary boundaries
- **Command:** `make eval-scientific-constraints`

This checks stable constraint IDs (genus→no strain production, unknown feature→no compound confirmation, correlation→no causality, mention→no production, etc.) against **existing module outputs**. It does **not** replace runtime enforcement inside each module and does **not** constitute human empirical validation.

---

## Related Documents

- `docs/ANNOTATION_POLICY.md` — grades, metrics, pooling, blind export
- `docs/ANNOTATION_INSTRUCTIONS.md` — reviewer guidance
- `docs/SNAPSHOT_PUBLIC_REPO_AUDIT.md` — committed snapshot handling
- `docs/PHASE2_CLOSURE_AUDIT.md` — Phase 2 DoD status
