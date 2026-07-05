# Literature Source Adapter Policy

Phase 2 defines source adapter boundaries for future external literature ingestion. **No real PubMed, Crossref, OpenAlex, Europe PMC, or licensed full-text integration is implemented yet.**

## Implemented Today

- `SourceAdapter` protocol in `rhizonp.literature.adapters`
- `SyntheticLiteratureAdapter` for fixture-backed local development and tests
- Structured chunking and provenance fields on normalized records

## Adapter Contract

Every source adapter must implement:

```python
class SourceAdapter(Protocol):
    source_name: str

    def fetch(self, query: dict) -> list[RawLiteratureRecord]: ...
    def normalize(self, record: RawLiteratureRecord) -> NormalizedLiteratureRecord: ...
    def provenance(self, record: RawLiteratureRecord) -> dict: ...
```

Design requirements for future real adapters:

1. **Explicit provenance** — every fetched record must record source name, fetch timestamp, query parameters, and license/API terms version.
2. **Isolated network I/O** — HTTP clients must be injectable so unit tests never require live network calls.
3. **Rate-limit awareness** — adapters must expose configured request limits and backoff; callers must not hard-code credentials.
4. **No fake integration claims** — README, API docs, and provenance docs must not say a source is integrated until fetch + normalize + tests exist.
5. **License-first** — full text and metadata reuse must be checked against source terms before ingestion pipelines are enabled.

## Candidate External Sources (Not Implemented)

| Source | Primary use | Constraints to verify before implementation |
| --- | --- | --- |
| PubMed / NCBI E-utilities | Biomedical abstracts, PMIDs | [NCBI E-utilities policy](https://www.ncbi.nlm.nih.gov/home/about/policies/); rate limits; no bulk redistribution beyond permitted use |
| Crossref REST API | DOI metadata, titles, journals | [Crossref REST API terms](https://www.crossref.org/documentation/retrieve-metadata/rest-api/); polite pool / mailto usage |
| OpenAlex | Scholarly metadata graph | [OpenAlex API docs](https://docs.openalex.org/); rate limits; attribution |
| Licensed OA full text | Section-aware chunking | Publisher/license-specific; no automatic download without explicit license audit |

## Recommended First Real Adapter

When adding the first production adapter, prefer **Crossref metadata only**:

- Smaller scope than full-text ingestion
- Clear REST API and DOI-centric provenance
- Easy to mock with recorded HTTP fixtures
- Complements existing `papers.doi` and chunk trace fields

Do **not** start with simultaneous PubMed + Crossref + OpenAlex wrappers unless each has isolated tests and provenance documentation.

## Non-Goals for Phase 2

- Autonomous agent fetching
- Bulk corpus mirroring
- PDF OCR pipelines
- Claiming benchmark-quality retrieval from metadata-only adapters

These belong to later phases after taxonomy-aware evidence grading and evaluation baselines exist.
