#!/usr/bin/env bash
# Live API integration checks against a running RhizoNP Navigator server.
#
# Usage:
#   ./scripts/test_api_integration.sh
#   ./scripts/test_api_integration.sh --base-url http://127.0.0.1:8000
#   ./scripts/test_api_integration.sh --full   # also require DB-backed endpoints

set -euo pipefail

BASE_URL="http://127.0.0.1:8000"
FULL=0
PASS=0
FAIL=0
SKIP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:?missing value for --base-url}"
      shift 2
      ;;
    --full)
      FULL=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

pass() {
  PASS=$((PASS + 1))
  printf '  [PASS] %s\n' "$1"
}

fail() {
  FAIL=$((FAIL + 1))
  printf '  [FAIL] %s\n' "$1" >&2
}

skip() {
  SKIP=$((SKIP + 1))
  printf '  [SKIP] %s\n' "$1"
}

request() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local expected="${4:-200}"
  local label="$5"

  local tmp
  tmp="$(mktemp)"
  local code
  if [[ -n "${data}" ]]; then
    code="$(curl -sS -o "${tmp}" -w '%{http_code}' -X "${method}" \
      -H 'Content-Type: application/json' \
      -d "${data}" \
      "${BASE_URL}${path}")"
  else
    code="$(curl -sS -o "${tmp}" -w '%{http_code}' -X "${method}" "${BASE_URL}${path}")"
  fi

  if [[ "${code}" == "${expected}" ]]; then
    pass "${label} (${code})"
    cat "${tmp}"
  else
    fail "${label} (expected ${expected}, got ${code})"
    cat "${tmp}" >&2
    rm -f "${tmp}"
    return 1
  fi
  rm -f "${tmp}"
}

echo "[rhizonp] API integration test -> ${BASE_URL}"

request GET /api/v1/health "" 200 "health"

request POST /api/v1/taxonomy/grade \
  '{"query_taxon":"Streptomyces","literature_taxon":"Streptomyces hygroscopicus OS-2","observation_method":"16S genus-level"}' \
  200 "taxonomy grade"

request POST /api/v1/natural-products/link \
  '{"query_taxon":"Streptomyces","metabolite_name":"FixturePolyketide-A","observation_method":"16S genus-level"}' \
  200 "natural product link"

request POST /api/v1/own-data/pipeline \
  '{}' \
  200 "own-data pipeline"

request POST /api/v1/writer/answer \
  '{"question":"What is supported by the evidence?","evidence_items":[{"evidence_id":"00000000-0000-4000-8000-000000000001","claim_type":"association","predicate":"correlates_with","object_literal":"Feature_M123","evidence_tier":"same_genus","directness":"indirect","confidence":0.6,"supporting_span":"genus-level correlation only","provenance":{"fixture":true}}],"taxonomy_warnings":["Genus-level 16S cannot support strain-level production claims."],"limitations":["Correlation is not causation."],"use_llm":false}' \
  200 "writer answer"

if [[ "${FULL}" -eq 1 ]]; then
  request GET /api/v1/taxa/Streptomyces "" 200 "taxon lookup"
  request POST /api/v1/search \
    '{"query":"Streptomyces Feature_M123","top_k":2,"filters":{"sections":["results"],"source_types":["paper"],"dois":["10.0000/rhizonp.fixture.lit.001"],"journals":["fixture"],"taxa":["Streptomyces"],"compounds":["FixturePolyketide-A"],"host":["Synthetic plant"]}}' \
    200 "literature search"
else
  tmp="$(mktemp)"
  code="$(curl -sS -o "${tmp}" -w '%{http_code}' "${BASE_URL}/api/v1/taxa/Streptomyces")"
  rm -f "${tmp}"
  if [[ "${code}" == "200" ]]; then
    pass "taxon lookup (${code})"
    request POST /api/v1/search \
      '{"query":"Streptomyces Feature_M123","top_k":2,"filters":{"sections":["results"],"source_types":["paper"],"dois":["10.0000/rhizonp.fixture.lit.001"],"journals":["fixture"],"taxa":["Streptomyces"],"compounds":["FixturePolyketide-A"],"host":["Synthetic plant"]}}' \
      200 "literature search"
  else
    skip "DB-backed endpoints (taxon/search) — start PostgreSQL with './scripts/start.sh db' or './scripts/start.sh db && ./scripts/start.sh test-api --full'"
  fi
fi

echo
echo "[rhizonp] Summary: pass=${PASS} fail=${FAIL} skip=${SKIP}"
if [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi
