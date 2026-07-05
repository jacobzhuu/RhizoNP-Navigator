# Limitations

## Current MVP scope

- Natural product records come from local synthetic fixtures, not NPAtlas, MIBiG, Crossref, or OpenAlex.
- Literature retrieval uses synthetic and bounded PubMed corpus fixtures; production-scale indexing is not complete.
- Dense retrieval defaults to deterministic hashing embeddings unless optional model-backed providers are configured.
- LLM writer mode is optional and falls back to deterministic synthesis in offline/demo paths.
- Phase 2 empirical human labeling for the 543-item annotation task remains pending.

## Scientific boundaries

- Correlation or co-occurrence does not imply biochemical production or causation.
- Genus-level evidence is candidate-level only.
- Unknown LC-MS features must not be promoted to confirmed compound identities.
- Conflicting evidence returns `CONFLICTING_EVIDENCE` rather than a forced single answer.

## Operational boundaries

- Tests and demos are offline by default.
- Docker/PostgreSQL validation may require a running Docker daemon locally.
- Remote push to GitHub requires configured credentials in the local environment.
