#!/usr/bin/env bash
# One-click RhizoNP Navigator launcher.
#
# Usage:
#   ./scripts/start.sh              # setup (if needed) + optional DB + API server
#   ./scripts/start.sh setup        # conda env + pip install + .env
#   ./scripts/start.sh db           # PostgreSQL (Docker) + migrate + fixtures
#   ./scripts/start.sh api          # start FastAPI only (foreground)
#   ./scripts/start.sh test-api     # run API integration checks
#   ./scripts/start.sh smoke        # offline 3-case smoke test
#   ./scripts/start.sh demo         # full offline demo
#   ./scripts/start.sh e2e          # end-to-end evaluation suite
#   ./scripts/start.sh app          # API + Vite frontend (background)
#   ./scripts/start.sh stop         # stop background API and frontend
#   ./scripts/start.sh --verbose    # show full pip/migration output
#
# Environment variables:
#   RHIZONP_CONDA_ENV   conda env name (default: rhizonp)
#   RHIZONP_HOST        API bind host (default: 127.0.0.1)
#   RHIZONP_PORT        API bind port (default: 8000)
#   RHIZONP_FRONTEND_PORT  Vite dev port (default: 5173)
#   RHIZONP_SKIP_DB     set to 1 to skip Docker Postgres bootstrap
#   RHIZONP_VERBOSE     set to 1 for detailed command output

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
STEP=0
ENV_ENSURED=0

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

log() {
  printf '[rhizonp] %s\n' "$*"
}

step() {
  STEP=$((STEP + 1))
  printf '[rhizonp] (%d) %s\n' "${STEP}" "$*"
}

warn() {
  printf '[rhizonp][warn] %s\n' "$*" >&2
}

die() {
  printf '[rhizonp][error] %s\n' "$*" >&2
  exit 1
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
  log "${label} running in background (pid ${spawned_pid})"
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
    step "conda env '${ENV_NAME}' ready"
  else
    step "creating conda env '${ENV_NAME}'"
    if [[ "${VERBOSE}" -eq 1 ]]; then
      conda env create -f "${ROOT}/environment.yml"
    else
      conda env create -f "${ROOT}/environment.yml" >>"${BOOTSTRAP_LOG}" 2>&1
    fi
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
  log "dependencies OK"
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
  export DATABASE_URL="${DEFAULT_DATABASE_URL}"
  warn "DATABASE_URL unset; using Docker Compose default for this session."
}

docker_available() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

setup_db() {
  if [[ "${RHIZONP_SKIP_DB:-0}" == "1" ]]; then
    warn "RHIZONP_SKIP_DB=1; skipping database bootstrap."
    return 0
  fi

  if ! docker_available; then
    warn "Docker unavailable — stateless API only. Run './scripts/start.sh db' after Docker is up."
    return 0
  fi

  ensure_database_url
  step "starting PostgreSQL (docker compose)"
  (
    cd "${ROOT}"
    export DATABASE_URL
    if [[ "${VERBOSE}" -eq 1 ]]; then
      docker compose up -d postgres
    else
      docker compose up -d postgres >>"${BOOTSTRAP_LOG}" 2>&1
    fi
  )

  step "waiting for PostgreSQL"
  local ready=0
  for _ in $(seq 1 30); do
    if docker compose -f "${ROOT}/docker-compose.yml" exec -T postgres pg_isready -U rhizonp -d rhizonp >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  [[ "${ready}" -eq 1 ]] || die "PostgreSQL did not become ready within 30s."

  step "migrations and fixtures"
  (
    cd "${ROOT}"
    export DATABASE_URL
    run_cmd "alembic upgrade" alembic upgrade head
    run_cmd "demo fixtures" python -m scripts.load_demo_fixtures
    run_cmd "literature fixtures" python -m scripts.load_literature_fixtures
  )
  log "database OK"
}

stop_api() {
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}")"
    if kill -0 "${pid}" >/dev/null 2>&1; then
      step "stopping API (pid ${pid})"
      kill "${pid}" || true
      wait "${pid}" 2>/dev/null || true
    fi
    rm -f "${PID_FILE}"
  fi
}

stop_frontend() {
  if [[ -f "${FRONTEND_PID_FILE}" ]]; then
    local pid
    pid="$(cat "${FRONTEND_PID_FILE}")"
    if kill -0 "${pid}" >/dev/null 2>&1; then
      step "stopping frontend (pid ${pid})"
      kill "${pid}" || true
      wait "${pid}" 2>/dev/null || true
    fi
    rm -f "${FRONTEND_PID_FILE}"
  fi
}

stop_all() {
  stop_frontend
  stop_api
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
  spawn_detached "API" "${PID_FILE}" "${LOG_FILE}" \
    python -m uvicorn rhizonp.api.app:app --app-dir src --host "${HOST}" --port "${PORT}" --log-level warning
  log "  docs  → http://${HOST}:${PORT}/docs"
  log "  logs  → ${LOG_FILE}"
}

wait_for_api() {
  local url="http://${HOST}:${PORT}/api/v1/health"
  step "waiting for API health"
  for _ in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      log "API healthy"
      return 0
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
  spawn_detached "frontend" "${FRONTEND_PID_FILE}" "${FRONTEND_LOG_FILE}" \
    npm run dev -- --host "${HOST}" --port "${FRONTEND_PORT}"
  log "  app   → http://${HOST}:${FRONTEND_PORT}/"
  log "  logs  → ${FRONTEND_LOG_FILE}"
}

wait_for_frontend() {
  local url="http://${HOST}:${FRONTEND_PORT}/"
  step "waiting for frontend"
  for _ in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      log "frontend ready"
      return 0
    fi
    sleep 1
  done
  die "Frontend not ready at ${url}. See ${FRONTEND_LOG_FILE}"
}

cmd_setup() {
  : >"${BOOTSTRAP_LOG}"
  ensure_conda_env
  ensure_project_deps
  ensure_env_file
  log "setup complete — activate with: conda activate ${ENV_NAME}"
}

cmd_all() {
  : >"${BOOTSTRAP_LOG}"
  cmd_setup
  setup_db
  start_api_background
  wait_for_api
  step "API integration checks"
  "${ROOT}/scripts/test_api_integration.sh" --base-url "http://${HOST}:${PORT}"
  printf '\n[rhizonp] Ready.\n'
  log "  stop API → ./scripts/start.sh stop"
  log "  tail log → tail -f ${LOG_FILE}"
}

cmd_app() {
  : >"${BOOTSTRAP_LOG}"
  ensure_conda_env
  ensure_env_file
  ensure_database_url
  start_api_background
  wait_for_api
  start_frontend_background
  wait_for_frontend
  printf '\n[rhizonp] Full-stack dev ready.\n'
  log "  workspace → http://${HOST}:${FRONTEND_PORT}/"
  log "  API docs  → http://${HOST}:${PORT}/docs"
  log "  stop all  → ./scripts/start.sh stop"
}

cmd="${1:-all}"
case "${cmd}" in
  setup) cmd_setup ;;
  db) ensure_conda_env; ensure_env_file; : >"${BOOTSTRAP_LOG}"; setup_db ;;
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
  app) cmd_app ;;
  stop) stop_all ;;
  all) cmd_all ;;
  *)
    die "Unknown command: ${cmd}. Try: setup | db | api | app | test-api | smoke | demo | e2e | stop | all"
    ;;
esac
