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

## Related Documents

- `docs/ANNOTATION_POLICY.md` — grades, metrics, pooling, blind export
- `docs/ANNOTATION_INSTRUCTIONS.md` — reviewer guidance
- `docs/SNAPSHOT_PUBLIC_REPO_AUDIT.md` — committed snapshot handling
- `docs/PHASE2_CLOSURE_AUDIT.md` — Phase 2 DoD status
