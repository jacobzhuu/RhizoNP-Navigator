#!/usr/bin/env bash
# Expose the local RhizoNP workspace via Cloudflare quick Tunnel (trycloudflare.com).
#
# Usage:
#   ./scripts/tunnel.sh              # tunnel only (app must already be running)
#   ./scripts/tunnel.sh --start      # bootstrap full stack, then tunnel
#   make tunnel
#   make share                       # start app + tunnel
#
# Environment:
#   RHIZONP_HOST            frontend/API bind host (default: 127.0.0.1)
#   RHIZONP_FRONTEND_PORT     Vite dev port (default: 5173)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${RHIZONP_HOST:-127.0.0.1}"
FRONTEND_PORT="${RHIZONP_FRONTEND_PORT:-5173}"
LOCAL_URL="http://${HOST}:${FRONTEND_PORT}"
AUTO_START=0

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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start|-s)
      AUTO_START=1
      shift
      ;;
    --help|-h)
      sed -n '2,12p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      die "Unknown option: $1 (try --help)"
      ;;
  esac
done

ensure_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    return 0
  fi
  die "cloudflared not found. Install it first:
  macOS:  brew install cloudflared
  Linux:  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
}

wait_for_frontend() {
  log "waiting for frontend at ${LOCAL_URL}"
  for _ in $(seq 1 60); do
    if curl -fsS "${LOCAL_URL}/" >/dev/null 2>&1; then
      log "frontend ready"
      return 0
    fi
    sleep 1
  done
  die "Frontend not reachable at ${LOCAL_URL}. Run 'make start' or './scripts/tunnel.sh --start' first."
}

start_stack() {
  log "starting full stack (browser auto-open disabled)"
  RHIZONP_OPEN_BROWSER=0 "${ROOT}/scripts/start.sh" app
}

run_tunnel() {
  log "opening Cloudflare quick Tunnel → ${LOCAL_URL}"
  log "share the https://….trycloudflare.com URL printed below (Ctrl+C to stop)"
  printf '\n'

  # cloudflared logs to stderr; tee keeps a readable public URL in the output.
  cloudflared tunnel --url "${LOCAL_URL}" 2>&1 | while IFS= read -r line; do
    printf '%s\n' "${line}"
    if [[ "${line}" =~ (https://[a-zA-Z0-9-]+\.trycloudflare\.com) ]]; then
      printf '\n[rhizonp] Public workspace URL: %s\n\n' "${BASH_REMATCH[1]}"
    fi
  done
}

if [[ "${AUTO_START}" -eq 1 ]]; then
  start_stack
fi

ensure_cloudflared
wait_for_frontend
run_tunnel
