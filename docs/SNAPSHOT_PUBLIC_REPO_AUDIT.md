# PubMed Snapshot Public Repository Audit

Conservative engineering review of committed corpus data under
`data/snapshots/pubmed/rhizonp_domain_v1/`. This is **not** legal advice.

---

## Committed Files

| File | Purpose |
| --- | --- |
| `corpus.json` | Metadata snapshot of 149 PubMed records |
| `manifest.json` | Checksums, record count, query-config provenance |

---

## Fields Present Per Record

Each record in `corpus.json` includes:

| Field | Committed | Notes |
| --- | --- | --- |
| `pmid` | Yes | Public PubMed identifier |
| `doi` | When available | Public bibliographic identifier |
| `title` | Yes | PubMed metadata |
| `abstract` | Yes | PubMed metadata text (not full text) |
| `year`, `journal` | Yes | Bibliographic metadata |
| `source_url` | Yes | PubMed article URL |
| `license` | Yes | Set to `metadata_only` |
| `metadata` | Yes | Source type flags |
| `provenance` | Yes | Fetch timestamp, query, adapter metadata |
| `sections` | Yes | Empty for metadata-only fetch |
| Full text / PDF | **No** | Not fetched |

Snapshot metadata flags: `metadata_only=true`, `full_text=false`.

---

## Source and Provenance

- Source: NCBI E-utilities (`PubMedEutilitiesAdapter`)
- Fetch date: recorded in manifest (`2026-07-05T06:10:12+00:00`)
- Query config: `data/eval/domain_corpus_queries.json` (checksum in manifest)
- Deduplication: by PMID, first query wins

---

## Regeneration Alternative

The repository **can** regenerate the corpus locally without committing `corpus.json`:

1. Keep `domain_corpus_queries.json` and manifest/query provenance under version control.
2. Run `make fetch-domain-corpus` with network access and NCBI policy settings.
3. Verify checksums via `manifest.json`.

Committed PMIDs are also listed in `corpus.json` metadata `query_runs[].pmids` for audit.

---

## Conservative Public-Repository Recommendation

For public Git hosting:

1. **Preferred:** commit only `manifest.json` + query config; regenerate `corpus.json` locally.
2. **If keeping `corpus.json` public:** treat it as redistributable PubMed metadata only;
   retain provenance fields; do not add full text.
3. **Review before wider release:** confirm institutional/policy constraints on abstract
   redistribution and NCBI usage compliance.
4. **Do not delete automatically** — teams may rely on the committed snapshot for offline
   reproducibility; choose per deployment policy.

This audit documents current state; it does not mandate removal of the snapshot.
