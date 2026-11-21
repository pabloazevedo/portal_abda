#!/usr/bin/env bash
# Esteira de segurança. Roda só em containers Docker.
# Uso: scripts/security/pipeline.sh [fast|all|gitleaks|bandit|semgrep|pip-audit|npm-audit|hadolint|trivy-fs|image|dast]
#   fast = só scanners paralelos (~30s) — ideal no pre-commit
#   all  = fast + image + dast (~2–3 min)
# PARALLEL_JOBS controla o pool (default = nproc).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
REPORTS="$ROOT/security-reports"
mkdir -p "$REPORTS"
chmod 777 "$REPORTS" 2>/dev/null || true

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-portal_abda}"
IMAGE="${APP_IMAGE:-portal_abda-app:local}"
STAGE="${1:-all}"
FAIL=0
SUMMARY="$REPORTS/pipeline-summary.txt"
: > "$SUMMARY"

PARALLEL_JOBS="${PARALLEL_JOBS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)}"

log() { printf '\n== %s ==\n' "$*"; }

mark() {
  local name="$1" code="$2"
  if [[ "$code" -eq 0 ]]; then
    echo "PASS  $name" | tee -a "$SUMMARY"
  else
    echo "FAIL  $name (exit $code)" | tee -a "$SUMMARY"
    FAIL=1
  fi
}

need_docker() {
  if ! docker info >/dev/null 2>&1; then
    echo "Docker não está acessível. A esteira roda dentro de containers." >&2
    exit 1
  fi
}

run_gitleaks() {
  log "Gitleaks"
  docker run --rm \
    -v "$ROOT:/repo" -w /repo \
    ghcr.io/gitleaks/gitleaks:latest \
    detect --source /repo \
    --report-format json \
    --report-path /repo/security-reports/gitleaks.json
}

run_bandit() {
  log "Bandit"
  docker run --rm -v "$ROOT:/src" -w /src python:3.12-slim \
    bash -lc "pip install -q bandit && bandit -r app -ll -f json -o security-reports/bandit.json"
}

run_semgrep() {
  log "Semgrep"
  docker run --rm -v "$ROOT:/src" semgrep/semgrep \
    semgrep scan \
    --config p/python --config p/owasp-top-ten --config p/secrets \
    --metrics=off --error --json \
    --output /src/security-reports/semgrep.json \
    /src/app /src/Dockerfile
}

run_pip_audit() {
  log "pip-audit"
  docker run --rm -v "$ROOT:/src" -w /src python:3.12-slim \
    bash -lc "pip install -q pip-audit && pip-audit -r requirements.txt --format json -o security-reports/pip-audit.json"
}

run_npm_audit() {
  log "npm audit"
  docker run --rm \
    -v "$ROOT/frontend:/src" -w /src \
    -v "$REPORTS:/reports" \
    node:20-alpine \
    sh -lc "npm audit --omit=dev --audit-level=high --json > /reports/npm-audit.json"
}

run_hadolint() {
  log "Hadolint"
  docker run --rm -i hadolint/hadolint \
    hadolint --failure-threshold error -f json - \
    < "$ROOT/Dockerfile" > "$REPORTS/hadolint.json"
}

run_trivy_fs() {
  log "Trivy filesystem"
  docker run --rm -v "$ROOT:/src" aquasec/trivy:latest \
    fs --scanners vuln,secret,misconfig \
    --ignore-unfixed --severity HIGH,CRITICAL --exit-code 1 \
    --skip-dirs security-reports --skip-dirs frontend/node_modules --skip-dirs .git \
    --skip-files .env \
    --format json -o /src/security-reports/trivy-fs.json /src
}

run_image() {
  log "Build + Trivy image"
  docker build -t "$IMAGE" "$ROOT" || return $?
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$REPORTS:/reports" \
    aquasec/trivy:latest \
    image --ignore-unfixed --severity HIGH,CRITICAL --exit-code 1 \
    --format json -o /reports/trivy-image.json "$IMAGE"
}

wait_health() {
  local i
  for i in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:${APP_PORT:-8000}/healthz" >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
  done
  return 1
}

run_dast() {
  log "OWASP ZAP baseline"
  local started=0
  if ! curl -fsS "http://127.0.0.1:${APP_PORT:-8000}/healthz" >/dev/null 2>&1; then
    if [[ ! -f "$ROOT/.env" ]]; then
      cp "$ROOT/.env.example" "$ROOT/.env"
    fi
    docker compose up -d --build
    started=1
    if ! wait_health; then
      echo "A aplicação não respondeu em /healthz." >&2
      if [[ "$started" -eq 1 ]]; then
        docker compose down
      fi
      return 1
    fi
  fi
  docker run --rm \
    --network "${COMPOSE_PROJECT_NAME}_default" \
    -v "$REPORTS:/zap/wrk:rw" \
    ghcr.io/zaproxy/zaproxy:stable \
    zap-baseline.py -t "http://orchestra_app:8000" \
    -J zap-baseline.json -w zap-baseline.md -I -m 5
  local zap_code=$?
  if [[ "$started" -eq 1 ]]; then
    docker compose down
  fi
  return "$zap_code"
}

run_stage_one() {
  case "$1" in
    gitleaks) run_gitleaks ;;
    bandit) run_bandit ;;
    semgrep) run_semgrep ;;
    pip-audit) run_pip_audit ;;
    npm-audit) run_npm_audit ;;
    hadolint) run_hadolint ;;
    trivy-fs) run_trivy_fs ;;
    image) run_image ;;
    dast) run_dast ;;
    *)
      echo "Etapa desconhecida: $1" >&2
      return 2
      ;;
  esac
}

run_and_mark() {
  local stage="$1" code
  run_stage_one "$stage"
  code=$?
  mark "$stage" "$code"
  return "$code"
}

# Pool com no máximo PARALLEL_JOBS jobs; summary na ordem canônica.
run_parallel() {
  local -a stages=("$@")
  local -a pids=()
  local stage pid code
  local tmpdir
  tmpdir="$(mktemp -d "$REPORTS/parallel.XXXXXX")"

  # Job control necessário para `jobs -rp` / `wait -n` limitarem o pool.
  set -m

  log "Paralelo (${#stages[@]} etapas, até ${PARALLEL_JOBS} jobs)"
  echo "PARALLEL_JOBS=$PARALLEL_JOBS stages=${stages[*]}"

  for stage in "${stages[@]}"; do
    while [[ "$(jobs -rp | wc -l | tr -d ' ')" -ge "$PARALLEL_JOBS" ]]; do
      wait -n 2>/dev/null || wait || true
    done
    (
      set +e
      run_stage_one "$stage"
      echo $? > "$tmpdir/$stage.exit"
    ) > "$tmpdir/$stage.log" 2>&1 &
    pids+=("$!")
  done

  for pid in "${pids[@]}"; do
    wait "$pid" || true
  done

  set +m

  for stage in "${stages[@]}"; do
    echo "---- $stage ----"
    cat "$tmpdir/$stage.log" 2>/dev/null || true
    code="$(cat "$tmpdir/$stage.exit" 2>/dev/null || echo 1)"
    mark "$stage" "$code"
  done
  rm -rf "$tmpdir"
}

run_stage() {
  case "$1" in
    gitleaks|bandit|semgrep|pip-audit|npm-audit|hadolint|trivy-fs|image|dast)
      run_and_mark "$1" || true
      ;;
    fast)
      # Commit-time: sem docker build / ZAP
      run_parallel gitleaks bandit semgrep pip-audit npm-audit hadolint trivy-fs
      ;;
    all)
      run_parallel gitleaks bandit semgrep pip-audit npm-audit hadolint trivy-fs
      run_and_mark image || true
      run_and_mark dast || true
      ;;
    *)
      echo "Etapa desconhecida: $1" >&2
      echo "Etapas: fast all gitleaks bandit semgrep pip-audit npm-audit hadolint trivy-fs image dast" >&2
      exit 2
      ;;
  esac
}

need_docker
run_stage "$STAGE"
echo
echo "Resumo em $SUMMARY"
cat "$SUMMARY"
exit "$FAIL"
