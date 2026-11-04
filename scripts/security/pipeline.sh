#!/usr/bin/env bash
# Esteira de segurança. Roda só em containers Docker.
# Uso: scripts/security/pipeline.sh [all|gitleaks|bandit|semgrep|pip-audit|npm-audit|hadolint|trivy-fs|image|dast]
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
  mark gitleaks $?
}

run_bandit() {
  log "Bandit"
  docker run --rm -v "$ROOT:/src" -w /src python:3.12-slim \
    bash -lc "pip install -q bandit && bandit -r app -ll -f json -o security-reports/bandit.json"
  mark bandit $?
}

run_semgrep() {
  log "Semgrep"
  docker run --rm -v "$ROOT:/src" semgrep/semgrep \
    semgrep scan \
    --config p/python --config p/owasp-top-ten --config p/secrets \
    --metrics=off --error --json \
    --output /src/security-reports/semgrep.json \
    /src/app /src/Dockerfile
  mark semgrep $?
}

run_pip_audit() {
  log "pip-audit"
  docker run --rm -v "$ROOT:/src" -w /src python:3.12-slim \
    bash -lc "pip install -q pip-audit && pip-audit -r requirements.txt --format json -o security-reports/pip-audit.json"
  mark pip-audit $?
}

run_npm_audit() {
  log "npm audit"
  docker run --rm \
    -v "$ROOT/frontend:/src" -w /src \
    -v "$REPORTS:/reports" \
    node:20-alpine \
    sh -lc "npm audit --omit=dev --audit-level=high --json > /reports/npm-audit.json"
  mark npm-audit $?
}

run_hadolint() {
  log "Hadolint"
  docker run --rm -i hadolint/hadolint \
    hadolint --failure-threshold error -f json - \
    < "$ROOT/Dockerfile" > "$REPORTS/hadolint.json"
  mark hadolint $?
}

run_trivy_fs() {
  log "Trivy filesystem"
  docker run --rm -v "$ROOT:/src" aquasec/trivy:latest \
    fs --scanners vuln,secret,misconfig \
    --ignore-unfixed --severity HIGH,CRITICAL --exit-code 1 \
    --skip-dirs security-reports --skip-dirs frontend/node_modules --skip-dirs .git \
    --skip-files .env \
    --format json -o /src/security-reports/trivy-fs.json /src
  mark trivy-fs $?
}

run_image() {
  log "Build + Trivy image"
  docker build -t "$IMAGE" "$ROOT"
  local build_code=$?
  if [[ "$build_code" -ne 0 ]]; then
    mark image "$build_code"
    return
  fi
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$REPORTS:/reports" \
    aquasec/trivy:latest \
    image --ignore-unfixed --severity HIGH,CRITICAL --exit-code 1 \
    --format json -o /reports/trivy-image.json "$IMAGE"
  mark image $?
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
      mark dast 1
      if [[ "$started" -eq 1 ]]; then
        docker compose down
      fi
      return
    fi
  fi
  docker run --rm \
    --network "${COMPOSE_PROJECT_NAME}_default" \
    -v "$REPORTS:/zap/wrk:rw" \
    ghcr.io/zaproxy/zaproxy:stable \
    zap-baseline.py -t "http://orchestra_app:8000" \
    -J zap-baseline.json -w zap-baseline.md -I -m 5
  local zap_code=$?
  mark dast "$zap_code"
  if [[ "$started" -eq 1 ]]; then
    docker compose down
  fi
}

run_stage() {
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
    all)
      run_gitleaks
      run_bandit
      run_semgrep
      run_pip_audit
      run_npm_audit
      run_hadolint
      run_trivy_fs
      run_image
      run_dast
      ;;
    *)
      echo "Etapa desconhecida: $1" >&2
      echo "Etapas: all gitleaks bandit semgrep pip-audit npm-audit hadolint trivy-fs image dast" >&2
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
