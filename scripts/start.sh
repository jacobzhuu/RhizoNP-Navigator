#!/usr/bin/env bash
# One-click RhizoNP Navigator launcher.
#
# Usage:
#   ./scripts/start.sh              # setup + DB + API + Vite frontend
#   ./scripts/start.sh setup        # conda env + pip install + .env
#   ./scripts/start.sh db           # PostgreSQL (Docker) + migrate + fixtures
#   ./scripts/start.sh api          # start FastAPI only (foreground)
#   ./scripts/start.sh test-api     # run API integration checks
#   ./scripts/start.sh smoke        # offline 3-case smoke test
#   ./scripts/start.sh demo         # full offline demo
#   ./scripts/start.sh e2e          # end-to-end evaluation suite
#   ./scripts/start.sh app          # same as default full-stack launch
#   ./scripts/start.sh prod         # production runtime mode (no browser, RHIZONP_RUNTIME_MODE=prod)
#   ./scripts/start.sh stop         # stop background API and frontend
#   ./scripts/start.sh share        # full stack + Cloudflare Tunnel (public URL)
#   ./scripts/start.sh tunnel       # Cloudflare Tunnel only (app must be running)
#   ./scripts/start.sh --verbose    # show full pip/migration output
#
# Environment variables:
#   RHIZONP_CONDA_ENV   conda env name (default: rhizonp)
#   RHIZONP_HOST        API bind host (default: 127.0.0.1)
#   RHIZONP_PORT        API bind port (default: 8000)
#   RHIZONP_FRONTEND_PORT  Vite dev port (default: 5173)
#   RHIZONP_SKIP_DB     set to 1 to skip Docker Postgres bootstrap
#   RHIZONP_SKIP_API_CHECKS  set to 1 to skip post-start integration checks (used by share)
#   RHIZONP_RUNTIME_MODE  dev|prod (default: dev)
#   RHIZONP_OPEN_BROWSER  set to 0 to avoid opening the workspace URL
#   RHIZONP_VERBOSE     set to 1 for detailed command output

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/log.sh
source "${ROOT}/scripts/lib/log.sh"

ENV_NAME="${RHIZONP_CONDA_ENV:-rhizonp}"
HOST="${RHIZONP_HOST:-127.0.0.1}"
PORT="${RHIZONP_PORT:-8000}"
FRONTEND_PORT="${RHIZONP_FRONTEND_PORT:-5173}"
PID_FILE="${ROOT}/.rhizonp-api.pid"
LOG_FILE="${ROOT}/.rhizonp-api.log"
FRONTEND_PID_FILE="${ROOT}/.rhizonp-frontend.pid"
FRONTEND_LOG_FILE="${ROOT}/.rhizonp-frontend.log"
BOOTSTRAP_LOG="${ROOT}/.rhizonp-bootstrap.log"
DEFAULT_DATABASE_URL="postgresql://rhizonp:rhizonp_dev@localhost:5432/rhizonp"
VERBOSE="${RHIZONP_VERBOSE:-0}"
OPEN_BROWSER="${RHIZONP_OPEN_BROWSER:-1}"
ENV_ENSURED=0
DB_BOOTSTRAPPED=0

while [[ $# -gt 0 && "${1}" == --* ]]; do
  case "$1" in
    --verbose|-v)
      VERBOSE=1
      shift
      ;;
    --quiet|-q)
      VERBOSE=0
      shift
      ;;
    *)
      break
      ;;
  esac
done

open_browser() {
  local url="$1"
  if [[ "${OPEN_BROWSER}" != "1" ]]; then
    return 0
  fi
  if command -v open >/dev/null 2>&1; then
    open "${url}" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${url}" >/dev/null 2>&1 || true
  else
    warn "No browser opener found; open ${url} manually."
  fi
}

spawn_detached() {
  local label="$1"
  local pid_file="$2"
  local log_file="$3"
  shift 3
  : >"${log_file}"
  python - "${pid_file}" "${log_file}" "$@" <<'PY'
import subprocess
import sys
from pathlib import Path

pid_file, log_file = sys.argv[1], sys.argv[2]
command = sys.argv[3:]
with open(log_file, "a", encoding="utf-8") as log_handle:
    process = subprocess.Popen(
        command,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
Path(pid_file).write_text(str(process.pid), encoding="utf-8")
PY
  local spawned_pid
  spawned_pid="$(cat "${pid_file}")"
  step_ok "${label} running in background (pid ${spawned_pid})"
}

run_cmd() {
  local label="$1"
  shift
  if [[ "${VERBOSE}" -eq 1 ]]; then
    log "${label} ..."
    "$@"
    return $?
  fi
  if "$@" >>"${BOOTSTRAP_LOG}" 2>&1; then
    return 0
  fi
  warn "${label} failed. Last lines:"
  tail -n 20 "${BOOTSTRAP_LOG}" >&2 || true
  warn "Full log: ${BOOTSTRAP_LOG}"
  return 1
}

conda_shell() {
  local base
  base="$(conda info --base 2>/dev/null)" || die "conda not found. Install Miniforge/Anaconda first."
  # shellcheck disable=SC1091
  source "${base}/etc/profile.d/conda.sh"
}

ensure_conda_env() {
  conda_shell
  if [[ "${ENV_ENSURED}" -eq 1 && "${CONDA_DEFAULT_ENV:-}" == "${ENV_NAME}" ]]; then
    return 0
  fi
  if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
    step "conda env '${ENV_NAME}'"
    step_ok "environment ready"
  else
    step "creating conda env '${ENV_NAME}'"
    if [[ "${VERBOSE}" -eq 1 ]]; then
      conda env create -f "${ROOT}/environment.yml"
    else
      conda env create -f "${ROOT}/environment.yml" >>"${BOOTSTRAP_LOG}" 2>&1
    fi
    step_ok "environment created"
  fi
  conda activate "${ENV_NAME}"
  ENV_ENSURED=1
}

ensure_project_deps() {
  step "checking Python dependencies"
  local pip_flags=(-q)
  [[ "${VERBOSE}" -eq 1 ]] && pip_flags=()
  run_cmd "pip install" python -m pip install "${pip_flags[@]}" --upgrade pip
  run_cmd "requirements install" python -m pip install "${pip_flags[@]}" -r "${ROOT}/requirements.txt"
  run_cmd "editable install" python -m pip install "${pip_flags[@]}" -e "${ROOT}[dev]"
  step_ok "dependencies installed"
}

ensure_env_file() {
  if [[ ! -f "${ROOT}/.env" ]]; then
    step "creating .env from .env.example"
    cp "${ROOT}/.env.example" "${ROOT}/.env"
  fi
}

read_env_value() {
  local key="$1"
  local file="${ROOT}/.env"
  [[ -f "${file}" ]] || return 0
  grep -E "^${key}=" "${file}" | tail -n1 | cut -d= -f2- || true
}

ensure_database_url() {
  local current
  current="$(read_env_value DATABASE_URL)"
  if [[ -n "${current}" ]]; then
    export DATABASE_URL="${current}"
    return 0
  fi

  local pg_user pg_db pg_password pg_host pg_port
  pg_user="$(read_env_value POSTGRES_USER)"
  pg_db="$(read_env_value POSTGRES_DB)"
  pg_password="$(read_env_value POSTGRES_PASSWORD)"
  pg_host="$(read_env_value POSTGRES_HOST)"
  pg_port="$(read_env_value POSTGRES_PORT)"

  if [[ -z "${pg_user}" && -z "${pg_db}" && -z "${pg_password}" && -z "${pg_host}" && -z "${pg_port}" ]]; then
    export DATABASE_URL="${DEFAULT_DATABASE_URL}"
    warn "DATABASE_URL unset; using Docker Compose default (${DEFAULT_DATABASE_URL})."
    return 0
  fi

  pg_user="${pg_user:-rhizonp}"
  pg_db="${pg_db:-rhizonp}"
  pg_password="${pg_password:-rhizonp_dev}"
  pg_host="${pg_host:-localhost}"
  pg_port="${pg_port:-5432}"

  export DATABASE_URL="postgresql://${pg_user}:${pg_password}@${pg_host}:${pg_port}/${pg_db}"
  warn "DATABASE_URL unset; derived from .env POSTGRES_* → postgresql://${pg_user}@${pg_host}:${pg_port}/${pg_db}"
}

docker_available() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

setup_db() {
  local require_db="${1:-0}"
  if [[ "${RHIZONP_SKIP_DB:-0}" == "1" ]]; then
    warn "RHIZONP_SKIP_DB=1; skipping database bootstrap."
    DB_BOOTSTRAPPED=0
    return 0
  fi

  if ! docker_available; then
    if [[ "${require_db}" == "1" ]]; then
      die "Docker is required for full-stack startup because PostgreSQL backs search and entity endpoints. Start Docker, or set RHIZONP_SKIP_DB=1 for stateless API/frontend only."
    fi
    warn "Docker unavailable — stateless API only. Run './scripts/start.sh db' after Docker is up."
    DB_BOOTSTRAPPED=0
    return 0
  fi

  ensure_database_url
  local pg_user pg_db
  pg_user="$(read_env_value POSTGRES_USER)"
  pg_db="$(read_env_value POSTGRES_DB)"
  pg_user="${pg_user:-rhizonp}"
  pg_db="${pg_db:-rhizonp}"

  step "PostgreSQL (docker compose)"
  (
    cd "${ROOT}"
    export DATABASE_URL
    if [[ "${VERBOSE}" -eq 1 ]]; then
      docker compose up -d postgres
    else
      docker compose up -d postgres >>"${BOOTSTRAP_LOG}" 2>&1
    fi
  )

  log_wait "waiting for PostgreSQL"
  local ready=0
  for _ in $(seq 1 30); do
    if docker compose -f "${ROOT}/docker-compose.yml" exec -T postgres pg_isready -U "${pg_user}" -d "${pg_db}" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  [[ "${ready}" -eq 1 ]] || die "PostgreSQL did not become ready within 30s."
  step_ok "PostgreSQL ready"

  step "migrations and fixtures"
  (
    cd "${ROOT}"
    export DATABASE_URL
    run_cmd "alembic upgrade" alembic upgrade head
    run_cmd "demo fixtures" python -m scripts.load_demo_fixtures
    if [[ -f "${ROOT}/data/snapshots/pubmed/rhizonp_domain_v1/corpus.json" ]]; then
      run_cmd "bounded PubMed corpus" python -m scripts.build_domain_corpus --ingest --remove-fixture-literature
    else
      warn "Bounded PubMed snapshot missing; falling back to synthetic literature fixture."
      run_cmd "literature fixtures" python -m scripts.load_literature_fixtures
    fi
    export LITERATURE_RETRIEVAL_PROFILE=standard_rag
    run_cmd "literature FAISS index" python -m scripts.build_literature_faiss_index --if-stale
  )
  step_ok "database ready"
  DB_BOOTSTRAPPED=1
}

stop_process() {
  local label="$1"
  local pid_file="$2"
  if [[ ! -f "${pid_file}" ]]; then
    return 0
  fi
  local pid
  pid="$(cat "${pid_file}")"
  if kill -0 "${pid}" >/dev/null 2>&1; then
    step "stopping ${label}"
    # spawn_detached uses start_new_session=True, so pid is the process-group leader.
    kill -TERM "-${pid}" 2>/dev/null || kill "${pid}" || true
    for _ in $(seq 1 10); do
      if ! kill -0 "${pid}" >/dev/null 2>&1; then
        break
      fi
      sleep 0.2
    done
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill -KILL "-${pid}" 2>/dev/null || kill -KILL "${pid}" || true
      wait "${pid}" 2>/dev/null || true
    fi
    step_ok "${label} stopped (pid ${pid})"
  fi
  rm -f "${pid_file}"
}

wait_for_port_free() {
  local port="$1"
  for _ in $(seq 1 25); do
    if ! lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
  done
  warn "port ${port} still in use; continuing anyway"
}

stop_api() {
  stop_process "API" "${PID_FILE}"
  wait_for_port_free "${PORT}"
}

stop_frontend() {
  stop_process "frontend" "${FRONTEND_PID_FILE}"
  wait_for_port_free "${FRONTEND_PORT}"
}

stop_all() {
  log_init
  log_banner "RhizoNP Navigator" "Stopping services"
  log_section "Shutdown"
  stop_frontend
  stop_api
  log_ok "all services stopped"
}

start_api_foreground() {
  ensure_conda_env
  ensure_env_file
  ensure_database_url
  cd "${ROOT}"
  export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
  step "starting API at http://${HOST}:${PORT} (Ctrl+C to stop)"
  exec python -m uvicorn rhizonp.api.app:app --app-dir src --host "${HOST}" --port "${PORT}" --reload --log-level info
}

start_api_background() {
  ensure_conda_env
  ensure_env_file
  ensure_database_url
  stop_api
  cd "${ROOT}"
  export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
  step "API server"
  spawn_detached "API" "${PID_FILE}" "${LOG_FILE}" \
    python -m uvicorn rhizonp.api.app:app --app-dir src --host "${HOST}" --port "${PORT}" --log-level warning
  log_detail "docs  → http://${HOST}:${PORT}/docs"
  log_detail "logs  → ${LOG_FILE}"
}

wait_for_api() {
  local url="http://${HOST}:${PORT}/api/v1/health"
  log_wait "waiting for API health at ${url}"
  local consecutive=0
  for _ in $(seq 1 30); do
    if [[ -f "${PID_FILE}" ]]; then
      local pid
      pid="$(cat "${PID_FILE}")"
      if ! kill -0 "${pid}" >/dev/null 2>&1; then
        warn "API process (pid ${pid}) exited early. Recent log:"
        tail -n 20 "${LOG_FILE}" >&2 || true
        die "API process exited before becoming ready. See ${LOG_FILE}"
      fi
    fi
    if curl -fsS "${url}" >/dev/null 2>&1; then
      consecutive=$((consecutive + 1))
      if [[ "${consecutive}" -ge 2 ]]; then
        step_ok "API healthy"
        return 0
      fi
    else
      consecutive=0
    fi
    sleep 1
  done
  die "API not ready at ${url}. See ${LOG_FILE}"
}

ensure_frontend_deps() {
  if [[ ! -d "${ROOT}/frontend/node_modules" ]]; then
    step "installing frontend dependencies (npm install)"
    if [[ "${VERBOSE}" -eq 1 ]]; then
      (cd "${ROOT}/frontend" && npm install)
    else
      (cd "${ROOT}/frontend" && npm install >>"${BOOTSTRAP_LOG}" 2>&1)
    fi
  fi
}

start_frontend_background() {
  if ! command -v npm >/dev/null 2>&1; then
    die "npm not found. Install Node.js to run the research workspace frontend."
  fi
  ensure_frontend_deps
  stop_frontend
  cd "${ROOT}/frontend"
  step "frontend dev server"
  spawn_detached "frontend" "${FRONTEND_PID_FILE}" "${FRONTEND_LOG_FILE}" \
    env VITE_API_PROXY_TARGET="http://${HOST}:${PORT}" \
    npm run dev -- --host "${HOST}" --port "${FRONTEND_PORT}"
  log_detail "app   → http://${HOST}:${FRONTEND_PORT}/"
  log_detail "logs  → ${FRONTEND_LOG_FILE}"
}

wait_for_frontend() {
  local url="http://${HOST}:${FRONTEND_PORT}/"
  log_wait "waiting for frontend at ${url}"
  for _ in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      step_ok "frontend ready"
      return 0
    fi
    sleep 1
  done
  die "Frontend not ready at ${url}. See ${FRONTEND_LOG_FILE}"
}

cmd_setup() {
  : >"${BOOTSTRAP_LOG}"
  log_init
  log_banner "RhizoNP Navigator" "Environment setup"
  log_section "Environment"
  ensure_conda_env
  ensure_project_deps
  ensure_env_file
  log_ok "setup complete — activate with: conda activate ${ENV_NAME}"
}

cmd_all() {
  cmd_app
}

cmd_app() {
  local subtitle="${1:-Full-stack development}"
  : >"${BOOTSTRAP_LOG}"
  log_init
  log_banner "RhizoNP Navigator" "${subtitle}"
  log_section "Environment"
  ensure_conda_env
  ensure_project_deps
  ensure_env_file
  log_section "Database"
  setup_db 1
  log_section "Services"
  start_api_background
  wait_for_api
  if [[ "${RHIZONP_SKIP_API_CHECKS:-0}" != "1" ]]; then
    log_section "API checks"
    if [[ "${DB_BOOTSTRAPPED}" -eq 1 ]]; then
      "${ROOT}/scripts/test_api_integration.sh" --full --base-url "http://${HOST}:${PORT}"
    else
      "${ROOT}/scripts/test_api_integration.sh" --base-url "http://${HOST}:${PORT}"
    fi
  fi
  start_frontend_background
  wait_for_frontend
  log_summary_box "Ready" \
    "Workspace" "http://${HOST}:${FRONTEND_PORT}/" \
    "API docs" "http://${HOST}:${PORT}/docs" \
    "Stop" "make stop" \
    "API log" "${LOG_FILE}" \
    "Web log" "${FRONTEND_LOG_FILE}"
  open_browser "http://${HOST}:${FRONTEND_PORT}/"
}

cmd_share() {
  RHIZONP_OPEN_BROWSER=0 RHIZONP_SKIP_API_CHECKS=1 cmd_app "Share via Cloudflare Tunnel"
  export RHIZONP_TUNNEL_AFTER_SHARE=1
  exec "${ROOT}/scripts/tunnel.sh"
}

cmd_prod() {
  export RHIZONP_RUNTIME_MODE=prod
  export RHIZONP_OPEN_BROWSER=0
  cmd_app "Production runtime"
}

cmd="${1:-app}"
case "${cmd}" in
  setup) cmd_setup ;;
  db) ensure_conda_env; ensure_env_file; : >"${BOOTSTRAP_LOG}"; setup_db 1 ;;
  api) start_api_foreground ;;
  test-api)
    ensure_conda_env
    "${ROOT}/scripts/test_api_integration.sh" --base-url "http://${HOST}:${PORT}"
    ;;
  smoke)
    ensure_conda_env
    cd "${ROOT}"
    make smoke
    ;;
  demo)
    ensure_conda_env
    cd "${ROOT}"
    make demo
    ;;
  e2e)
    ensure_conda_env
    cd "${ROOT}"
    make eval-end-to-end
    ;;
  app) cmd_app "${2:-}" ;;
  prod) cmd_prod ;;
  share) cmd_share ;;
  tunnel) exec "${ROOT}/scripts/tunnel.sh" ;;
  stop) stop_all ;;
  all) cmd_all ;;
  *)
    die "Unknown command: ${cmd}. Try: setup | db | api | app | prod | share | tunnel | test-api | smoke | demo | e2e | stop | all"
    ;;
esac
