# PubMed Snapshot Public Repository Audit

Conservative engineering review of snapshot data under
`data/snapshots/pubmed/rhizonp_domain_v1/`. This is **not** legal advice.

---

## Version-Control Policy (Current)

| File | Git status | Purpose |
| --- | --- | --- |
| `manifest.json` | **Committed** | Checksums, corpus metadata, query-config provenance |
| `pmids.json` | **Committed** | PMID list + record count (no titles/abstracts) |
| `domain_corpus_queries.json` | **Committed** (under `data/eval/`) | Regeneration query config |
| `corpus.json` | **Local-only** (gitignored) | Full metadata snapshot with titles/abstracts |

Regenerate locally:

```bash
make fetch-domain-corpus
```

Verify checksums against `manifest.json` when `corpus.json` is present.

---

## Fields in Local `corpus.json`

When regenerated locally, each record includes PMID, DOI, title, **abstract**, year,
journal, source URL, provenance, and `metadata_only=true` / `full_text=false`.

Abstracts are **not** committed to the public repository in the current configuration.

---

## Why PMID-Only Commit

- Supports offline PMID validation and audit without redistributing abstract text in git.
- Preserves reproducibility via query config + manifest checksums.
- Teams with network access regenerate abstract-bearing snapshots locally for annotation/export.

---

## Annotation Workflow Dependency

`make export-annotation-candidates` requires a local `corpus.json` (or equivalent ingest
source) because blind sheets include title and abstract text.

CI tests use small fixtures under `tests/fixtures/pubmed/` instead of the full snapshot.

---

## Conservative Recommendation

For public Git hosting:

1. Commit `manifest.json`, `pmids.json`, and query config.
2. Gitignore `corpus.json`; regenerate before annotation or evaluation on real corpus.
3. Review institutional constraints before redistributing PubMed metadata externally.

This audit documents engineering policy; it does not mandate deletion of local snapshots.
