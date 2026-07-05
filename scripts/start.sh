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
#
# Environment variables:
#   RHIZONP_CONDA_ENV   conda env name (default: rhizonp)
#   RHIZONP_HOST        API bind host (default: 127.0.0.1)
#   RHIZONP_PORT        API bind port (default: 8000)
#   RHIZONP_SKIP_DB     set to 1 to skip Docker Postgres bootstrap

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${RHIZONP_CONDA_ENV:-rhizonp}"
HOST="${RHIZONP_HOST:-127.0.0.1}"
PORT="${RHIZONP_PORT:-8000}"
PID_FILE="${ROOT}/.rhizonp-api.pid"
LOG_FILE="${ROOT}/.rhizonp-api.log"
DEFAULT_DATABASE_URL="postgresql://rhizonp:rhizonp_dev@localhost:5432/rhizonp"

log() {
  printf '[rhizonp] %s\n' "$*"
}

warn() {
  printf '[rhizonp][warn] %s\n' "$*" >&2
}

die() {
  printf '[rhizonp][error] %s\n' "$*" >&2
  exit 1
}

conda_shell() {
  local base
  base="$(conda info --base 2>/dev/null)" || die "conda not found. Install Miniforge/Anaconda first."
  # shellcheck disable=SC1091
  source "${base}/etc/profile.d/conda.sh"
}

ensure_conda_env() {
  conda_shell
  if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
    log "Using existing conda env: ${ENV_NAME}"
  else
    log "Creating conda env '${ENV_NAME}' from environment.yml ..."
    conda env create -f "${ROOT}/environment.yml"
  fi
  conda activate "${ENV_NAME}"
}

ensure_project_deps() {
  log "Installing/updating Python dependencies ..."
  python -m pip install --upgrade pip
  python -m pip install -r "${ROOT}/requirements.txt"
  python -m pip install -e "${ROOT}[dev]"
}

ensure_env_file() {
  if [[ ! -f "${ROOT}/.env" ]]; then
    log "Creating .env from .env.example"
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
  log "DATABASE_URL not set in .env; using Docker Compose default for this session."
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
    warn "Docker is unavailable. Stateless API endpoints will work; DB-backed endpoints need PostgreSQL."
    warn "Install Docker and re-run './scripts/start.sh db', or set DATABASE_URL in .env manually."
    return 0
  fi

  ensure_database_url
  log "Starting PostgreSQL via docker compose ..."
  (
    cd "${ROOT}"
    export DATABASE_URL
    docker compose up -d postgres
  )

  log "Waiting for PostgreSQL to become ready ..."
  for _ in $(seq 1 30); do
    if docker compose -f "${ROOT}/docker-compose.yml" exec -T postgres pg_isready -U rhizonp -d rhizonp >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  log "Running migrations and loading fixtures ..."
  (
    cd "${ROOT}"
    export DATABASE_URL
    alembic upgrade head
    python -m scripts.load_demo_fixtures
    python -m scripts.load_literature_fixtures
  )
  log "Database ready."
}

stop_api() {
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}")"
    if kill -0 "${pid}" >/dev/null 2>&1; then
      log "Stopping API process ${pid}"
      kill "${pid}" || true
      wait "${pid}" 2>/dev/null || true
    fi
    rm -f "${PID_FILE}"
  fi
}

start_api_foreground() {
  ensure_conda_env
  ensure_env_file
  ensure_database_url
  cd "${ROOT}"
  export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
  log "Starting API at http://${HOST}:${PORT} (Ctrl+C to stop)"
  exec python -m uvicorn rhizonp.api.app:app --app-dir src --host "${HOST}" --port "${PORT}" --reload
}

start_api_background() {
  ensure_conda_env
  ensure_env_file
  ensure_database_url
  stop_api
  cd "${ROOT}"
  export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
  nohup python -m uvicorn rhizonp.api.app:app --app-dir src --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
  echo $! >"${PID_FILE}"
  log "API started in background (pid $(cat "${PID_FILE}"))"
  log "Logs: ${LOG_FILE}"
  log "Docs: http://${HOST}:${PORT}/docs"
}

wait_for_api() {
  local url="http://${HOST}:${PORT}/api/v1/health"
  for _ in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "API did not become ready at ${url}. Check ${LOG_FILE}"
}

cmd_setup() {
  ensure_conda_env
  ensure_project_deps
  ensure_env_file
  log "Setup complete. Activate with: conda activate ${ENV_NAME}"
}

cmd_all() {
  cmd_setup
  setup_db
  start_api_background
  wait_for_api
  log "Running API integration checks ..."
  "${ROOT}/scripts/test_api_integration.sh" --base-url "http://${HOST}:${PORT}"
  log "Ready. API is running in background; stop with: kill \$(cat ${PID_FILE})"
}

cmd="${1:-all}"
case "${cmd}" in
  setup) cmd_setup ;;
  db) ensure_conda_env; ensure_env_file; setup_db ;;
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
  stop) stop_api ;;
  all) cmd_all ;;
  *)
    die "Unknown command: ${cmd}. Try: setup | db | api | test-api | smoke | demo | e2e | stop | all"
    ;;
esac
