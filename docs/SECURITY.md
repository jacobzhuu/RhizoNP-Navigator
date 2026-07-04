# Security

## Secrets

Do not commit API keys, model provider tokens, database passwords, or machine-local model paths.

Use `.env.example` as the template for local configuration:

```bash
cp .env.example .env
```

The `.env` file is ignored by Git. If a credential has ever appeared in repository history, rotate or revoke it in the external service. Removing the value from the working tree is not enough.

## Local Secret Scan

Run:

```bash
python -m scripts.check_no_secrets
```

This scanner is intentionally lightweight and repo-local. It detects common API-key-looking values and non-placeholder assignments to password/API-key/token fields in source, docs, and configuration files.

## CI Security Gate

The GitHub Actions workflow runs the same scanner before linting, type checking, and tests.

## Database Credentials

`docker-compose.yml` uses local-development defaults through environment-variable interpolation. Override them in `.env` for local work. Do not use those defaults for shared servers or production data.

## Data Boundary

Do not commit private omics datasets, unpublished biological results, or licensed literature full text unless the repository policy explicitly allows redistribution. Future ingestion code must preserve provenance and license metadata.
