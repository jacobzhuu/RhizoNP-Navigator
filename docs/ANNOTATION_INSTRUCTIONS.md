# Phase 2 Real PubMed Benchmark — Reviewer Instructions

Read `docs/ANNOTATION_POLICY.md` for metric semantics and workflow boundaries.

---

## What You Are Judging

You will grade paper relevance for fixed benchmark queries using **title and abstract only**.
Do not use retrieval scores, ranks, or external lookups during grading.

Each row is one `(query, paper)` pair identified by `annotation_item_id`.

---

## Grades

| Grade | When to use |
| --- | --- |
| **0** | Irrelevant — the paper does not meaningfully address the query. |
| **1** | Partially relevant — related topic or indirect evidence, but not a direct answer. |
| **2** | Directly relevant — the paper clearly addresses the query intent. |

### Examples

**Query:** `Streptomyces biocontrol soilborne plant pathogens`

- **2:** Reports a *Streptomyces* strain with demonstrated biocontrol against a soilborne pathogen.
- **1:** Discusses *Streptomyces* secondary metabolites or biocontrol generally without clear soilborne focus.
- **0:** Unrelated plant pathology, unrelated taxon, or methods paper with no biocontrol link.

**Query:** `rhizosphere microbiome metabolite profiling`

- **2:** Profiles rhizosphere metabolites linked to microbiome composition or function.
- **1:** Rhizosphere microbiome or metabolomics alone without clear connection.
- **0:** Non-rhizosphere system or no metabolite/microbiome link.

---

## Partial vs Direct Relevance

- **Direct (2):** A reasonable researcher would cite this paper when answering the query.
- **Partial (1):** Same broad domain, but missing key aspect of the query (taxon, compartment, phenotype, etc.).
- **Irrelevant (0):** Connection is speculative or absent from the abstract.

---

## Insufficient Abstract Information

If the abstract is missing or too vague:

- Grade **0** if you cannot establish relevance from title/abstract.
- Use **notes** to record `insufficient_abstract` or `title_only`.
- Do **not** fetch full text or external metadata.

---

## Uncertainty Handling

If uncertain between 1 and 2:

- Choose the lower grade unless the abstract explicitly supports the higher grade.
- Record uncertainty in **notes** (e.g. `uncertain_partial_vs_direct`).

---

## Notes Field

Use `notes` for:

- ambiguity rationale
- insufficient abstract
- taxon/compartment mismatch explaining a grade-1 decision
- anything that would help audit disagreements later

Do not include retrieval system names or scores.

---

## Evidence Boundary

Judge only from fields provided in the blind sheet:

- `query_text`
- `title`
- `abstract`
- `doi` (identifier only; do not browse)

No inference beyond title/abstract evidence.

---

## QC Duplicate Rows

Some exports may include hidden QC duplicates (same paper content under a different
`annotation_item_id`). Grade each row independently. Project maintainers reconcile
QC pairs before final import.

---

## After Review

Return the completed `blind_reviewer_sheet.csv` with `grade` filled (0, 1, or 2).
Do not edit `annotation_item_id`, `query_id`, or `pmid`.
