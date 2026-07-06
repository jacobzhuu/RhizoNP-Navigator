#!/usr/bin/env bash
# Live API integration checks against a running RhizoNP Navigator server.
#
# Usage:
#   ./scripts/test_api_integration.sh
#   ./scripts/test_api_integration.sh --base-url http://127.0.0.1:8000
#   ./scripts/test_api_integration.sh --full   # also require DB-backed endpoints
#   ./scripts/test_api_integration.sh --verbose  # dump full JSON responses

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/log.sh
source "${ROOT}/scripts/lib/log.sh"

BASE_URL="http://127.0.0.1:8000"
FULL=0
VERBOSE=0
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
    --verbose|-v)
      VERBOSE=1
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
  _log_prefix
  printf '      '
  _log_green
  printf '%s %s\n' "${_LOG_ICON_OK}" "$1"
  _log_reset
}

fail() {
  FAIL=$((FAIL + 1))
  _log_prefix
  printf '      ' >&2
  _log_red
  printf '%s %s\n' "${_LOG_ICON_FAIL}" "$1" >&2
  _log_reset
}

skip() {
  SKIP=$((SKIP + 1))
  _log_prefix
  printf '      '
  _log_yellow
  printf '%s %s\n' "${_LOG_ICON_SKIP}" "$1"
  _log_reset
}

summarize_response() {
  local label="$1"
  local file="$2"
  python - "$label" "$file" <<'PY'
import json
import sys

label, path = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as handle:
    payload = json.load(handle)

if label == "health":
    print(f"status={payload.get('status', '?')}")
elif label == "taxonomy grade":
    print(
        f"distance={payload.get('taxonomy_distance', '?')}, "
        f"tier={payload.get('evidence_tier', '?')}, "
        f"claim={payload.get('max_supported_claim', '?')}"
    )
elif label == "natural product link":
    rows = payload.get("rows") or []
    top = rows[0] if rows else {}
    print(
        f"rows={len(rows)}, top={top.get('compound_name', '?')} "
        f"({top.get('status', '?')})"
    )
elif label == "own-data pipeline":
    print(f"associations={payload.get('association_count', '?')}")
elif label == "writer answer":
    print(f"status={payload.get('status', '?')}")
elif label == "taxon lookup":
    print(f"taxon={payload.get('canonical_name', '?')}, rank={payload.get('rank', '?')}")
elif label == "literature search":
    results = payload.get("results") or []
    print(f"results={len(results)}, mode={payload.get('retrieval_mode', '?')}")
else:
    print("ok")
PY
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
      "${BASE_URL}${path}" 2>/dev/null)" || code="000"
  else
    code="$(curl -sS -o "${tmp}" -w '%{http_code}' -X "${method}" "${BASE_URL}${path}" 2>/dev/null)" || code="000"
  fi

  if [[ "${code}" == "${expected}" ]]; then
    local detail
    detail="$(summarize_response "${label}" "${tmp}" 2>/dev/null || echo "ok")"
    pass "${label} (${code}) — ${detail}"
    if [[ "${VERBOSE}" -eq 1 ]]; then
      cat "${tmp}"
      echo
    fi
  else
    fail "${label} (expected ${expected}, got ${code})"
    echo "--- response ---" >&2
    cat "${tmp}" >&2
    echo >&2
    rm -f "${tmp}"
    return 1
  fi
  rm -f "${tmp}"
}

printf '\n'
log_detail "target → ${BASE_URL}"
printf '\n'

request GET /api/v1/health "" 200 "health"

request POST /api/v1/taxonomy/grade \
  '{"query_taxon":"Streptomyces","literature_taxon":"Streptomyces hygroscopicus OS-2","observation_method":"16S genus-level"}' \
  200 "taxonomy grade"

request POST /api/v1/natural-products/link \
  '{"query_taxon":"Streptomyces sp. SANK 62799","metabolite_name":"A-503083 F","observation_method":"database record"}' \
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
    '{"query":"Streptomyces","top_k":2}' \
    200 "literature search"
else
  tmp="$(mktemp)"
  code="$(curl -sS -o "${tmp}" -w '%{http_code}' "${BASE_URL}/api/v1/taxa/Streptomyces" 2>/dev/null)" || code="000"
  if [[ "${code}" == "200" ]]; then
    detail="$(summarize_response "taxon lookup" "${tmp}" 2>/dev/null || echo "ok")"
    pass "taxon lookup (${code}) — ${detail}"
    rm -f "${tmp}"
    request POST /api/v1/search \
      '{"query":"Streptomyces","top_k":2}' \
      200 "literature search"
  else
    rm -f "${tmp}"
    skip "DB endpoints (taxon/search) — run './scripts/start.sh db' first"
  fi
fi

printf '\n'
if [[ "${FAIL}" -gt 0 ]]; then
  _log_prefix
  printf ' '
  _log_red
  printf '%s %d passed, %d failed, %d skipped\n' "${_LOG_ICON_FAIL}" "${PASS}" "${FAIL}" "${SKIP}"
  _log_reset
  exit 1
fi
log_ok "${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
