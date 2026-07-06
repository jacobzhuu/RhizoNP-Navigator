#!/usr/bin/env bash
# RhizoNP Navigator CLI logging helpers.
# Source from launcher scripts after setting ROOT:
#   source "${ROOT}/scripts/lib/log.sh"

: "${RHIZONP_LOG_PREFIX:=rhizonp}"

_LOG_COLOR=0
if [[ -t 1 && -z "${NO_COLOR:-}" && "${TERM:-}" != "dumb" ]]; then
  _LOG_COLOR=1
fi

_log_style() {
  if [[ "${_LOG_COLOR}" -eq 1 ]]; then
    printf '\033[%sm' "$1"
  fi
}

_log_reset() { _log_style 0; }
_log_bold() { _log_style 1; }
_log_dim() { _log_style 2; }
_log_cyan() { _log_style 36; }
_log_green() { _log_style 32; }
_log_yellow() { _log_style 33; }
_log_red() { _log_style 31; }
_log_blue() { _log_style 34; }

if locale charmap 2>/dev/null | grep -qi utf-8; then
  _LOG_ICON_OK="✓"
  _LOG_ICON_FAIL="✗"
  _LOG_ICON_WARN="!"
  _LOG_ICON_ARROW="→"
  _LOG_ICON_DOT="•"
  _LOG_ICON_SKIP="~"
  _LOG_ICON_SPIN="…"
else
  _LOG_ICON_OK="OK"
  _LOG_ICON_FAIL="X"
  _LOG_ICON_WARN="!"
  _LOG_ICON_ARROW="->"
  _LOG_ICON_DOT="*"
  _LOG_ICON_SKIP="~"
  _LOG_ICON_SPIN="..."
fi

STEP="${STEP:-0}"
_LOG_STEP_TS=0
_LOG_CMD_START=0

log_init() {
  STEP=0
  _LOG_STEP_TS=0
  _LOG_CMD_START="$(date +%s)"
}

_log_prefix() {
  _log_dim
  printf '[%s]' "${RHIZONP_LOG_PREFIX}"
  _log_reset
}

log() {
  _log_prefix
  printf ' '
  _log_cyan
  printf '%s %s' "${_LOG_ICON_ARROW}" "$*"
  _log_reset
  printf '\n'
}

log_detail() {
  printf '           '
  _log_dim
  printf '%s' "$*"
  _log_reset
  printf '\n'
}

log_ok() {
  _log_prefix
  printf ' '
  _log_green
  printf '%s %s' "${_LOG_ICON_OK}" "$*"
  _log_reset
  printf '\n'
}

step() {
  STEP=$((STEP + 1))
  _LOG_STEP_TS="$(date +%s)"
  _log_prefix
  printf ' '
  _log_bold
  printf '[%02d] ' "${STEP}"
  _log_reset
  printf '%s\n' "$*"
}

step_ok() {
  local msg="${1:-done}"
  local elapsed=""
  if [[ "${_LOG_STEP_TS}" -gt 0 ]]; then
    elapsed=" ($(( $(date +%s) - _LOG_STEP_TS ))s)"
  fi
  _log_prefix
  printf '      '
  _log_green
  printf '%s %s%s' "${_LOG_ICON_OK}" "${msg}" "${elapsed}"
  _log_reset
  printf '\n'
}

warn() {
  _log_prefix
  printf ' ' >&2
  _log_yellow
  printf '%s %s' "${_LOG_ICON_WARN}" "$*" >&2
  _log_reset
  printf '\n' >&2
}

die() {
  _log_prefix
  printf ' ' >&2
  _log_red
  printf '%s %s' "${_LOG_ICON_FAIL}" "$*" >&2
  _log_reset
  printf '\n' >&2
  exit 1
}

log_section() {
  local title="$1"
  printf '\n'
  _log_bold
  printf '  %s\n' "${title}"
  _log_reset
  _log_dim
  printf '  %s\n' "$(printf '─%.0s' {1..52})"
  _log_reset
}

log_banner() {
  local title="$1"
  local subtitle="${2:-}"
  local width=52
  local line
  line="$(printf '─%.0s' $(seq 1 $width))"

  printf '\n'
  _log_cyan
  printf '  ╭%s╮\n' "${line}"
  _log_reset
  _log_bold
  printf '  │  %-50s│\n' "${title}"
  _log_reset
  if [[ -n "${subtitle}" ]]; then
    _log_dim
    printf '  │  %-50s│\n' "${subtitle}"
    _log_reset
  fi
  _log_cyan
  printf '  ╰%s╯\n' "${line}"
  _log_reset
  printf '\n'
}

log_kv() {
  local key="$1"
  local value="$2"
  printf '  %-12s' "${key}"
  _log_cyan
  printf '%s' "${value}"
  _log_reset
  printf '\n'
}

log_summary_box() {
  local title="${1:-Ready}"
  local width=52
  local line
  line="$(printf '─%.0s' $(seq 1 $width))"

  printf '\n'
  _log_green
  local title_pad=$((width - ${#title} - 1))
  printf '  ╭─ %s %s╮\n' "${title}" "$(printf '─%.0s' $(seq 1 $title_pad))"
  _log_reset
  shift
  while [[ $# -gt 0 ]]; do
    local key="$1"
    local value="$2"
    shift 2
    local inner="${key}  ${value}"
    local pad=$((width - ${#inner} + 2))
    [[ "${pad}" -lt 1 ]] && pad=1
    _log_green
    printf '  │  %s%*s│\n' "${inner}" "${pad}" ''
    _log_reset
  done
  _log_green
  printf '  ╰%s╯\n' "${line}"
  _log_reset
  if [[ "${_LOG_CMD_START}" -gt 0 ]]; then
    _log_dim
    printf '  finished in %ds\n' "$(( $(date +%s) - _LOG_CMD_START ))"
    _log_reset
  fi
  printf '\n'
}

log_wait() {
  _log_prefix
  printf ' '
  _log_dim
  printf '%s %s' "${_LOG_ICON_SPIN}" "$*"
  _log_reset
  printf '\n'
}
