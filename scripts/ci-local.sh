#!/usr/bin/env bash
# scripts/ci-local.sh — run the same checks GitHub Actions runs, locally.
#
# Mirrors .github/workflows/ci.yml so you can know the verdict BEFORE
# pushing. Order matches CI: fastest signal first.
#
# Usage:
#   ./scripts/ci-local.sh                 # both jobs
#   ./scripts/ci-local.sh --frontend      # tsc + eslint only (fast, ~30s)
#   ./scripts/ci-local.sh --backend       # pytest only (needs docker compose up)
#   ./scripts/ci-local.sh --skip-eslint   # frontend without eslint
#
# Exits non-zero on first failure so you can `&&` it into a push pipeline:
#   ./scripts/ci-local.sh && git push

set -u  # undefined var = error; do NOT set -e — we want to count failures

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
DIM='\033[2m'
RESET='\033[0m'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_frontend=true
run_backend=true
skip_eslint=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --frontend) run_backend=false; shift ;;
    --backend)  run_frontend=false; shift ;;
    --skip-eslint) skip_eslint=true; shift ;;
    -h|--help)
      sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
done

fails=()

step() {
  printf "${DIM}→${RESET} %s ${DIM}…${RESET}\n" "$1"
}

ok() {
  printf "${GREEN}✓${RESET} %s\n" "$1"
}

fail() {
  printf "${RED}✗${RESET} %s\n" "$1"
  fails+=("$1")
}

# ---------- Frontend ----------
if $run_frontend; then
  echo ""
  echo "════════ frontend ════════"
  cd "$REPO_ROOT/frontend"

  step "npx tsc --noEmit"
  if npx tsc --noEmit; then ok "tsc"; else fail "tsc"; fi

  if ! $skip_eslint; then
    step "npx eslint"
    if npx eslint; then ok "eslint"; else fail "eslint"; fi
  fi
fi

# ---------- Backend ----------
if $run_backend; then
  echo ""
  echo "════════ backend ════════"
  cd "$REPO_ROOT/backend"

  # The CI workflow spins up TimescaleDB as a service container. Locally
  # we expect `docker compose up -d postgres` (or your own running pg)
  # to already be available. Sanity-check before pytest so we fail loud.
  if ! python -c "import psycopg2; psycopg2.connect('${DATABASE_URL_SYNC:-postgresql://sandbelt:sandbelt_test@localhost:5432/sandbelt_db}')" 2>/dev/null; then
    printf "${YELLOW}!${RESET} cannot reach Postgres at the configured DATABASE_URL_SYNC\n"
    printf "  Run ${DIM}docker compose up -d postgres${RESET} (or set DATABASE_URL_SYNC) then retry.\n"
    fail "backend prerequisite (Postgres unreachable)"
  else
    step "pytest -m \"not slow\""
    if pytest -m "not slow" -q; then ok "pytest"; else fail "pytest"; fi
  fi
fi

# ---------- Verdict ----------
echo ""
if [[ ${#fails[@]} -eq 0 ]]; then
  printf "${GREEN}✓ all checks passed — CI should be green${RESET}\n"
  exit 0
else
  printf "${RED}✗ ${#fails[@]} step(s) failed:${RESET}\n"
  for f in "${fails[@]}"; do echo "  - $f"; done
  printf "\n${YELLOW}Fix locally, then push.${RESET}\n"
  exit 1
fi
