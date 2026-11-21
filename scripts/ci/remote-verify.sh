#!/usr/bin/env bash
# Sincroniza o repo para o Ubuntu e valida lá.
# VERIFY_MODE=fast (default) → scanners paralelos + Android  (~40–60s)
# VERIFY_MODE=full            → + image Trivy + ZAP DAST     (~2–3 min)
# Mac = só código. Host: 192.168.50.32 (ub2404202405).
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-192.168.50.32}"
REMOTE_USER="${REMOTE_USER:-pablo}"
REMOTE="${REMOTE_USER}@${REMOTE_HOST}"
REMOTE_DIR="${REMOTE_DIR:-/home/pablo/git/portal_abda}"
ROOT="$(git rev-parse --show-toplevel)"
SKIP_SECURITY="${SKIP_SECURITY:-0}"
SKIP_ANDROID="${SKIP_ANDROID:-0}"
VERIFY_MODE="${VERIFY_MODE:-fast}"

case "$VERIFY_MODE" in
  fast) PIPELINE_STAGE=fast ;;
  full|all) PIPELINE_STAGE=all ;;
  *)
    echo "VERIFY_MODE inválido: $VERIFY_MODE (use fast|full)" >&2
    exit 2
    ;;
esac

echo "==> rsync → $REMOTE:$REMOTE_DIR (VERIFY_MODE=$VERIFY_MODE)"
rsync -az --delete \
  --exclude '.git/' \
  --exclude 'node_modules/' \
  --exclude 'frontend/node_modules/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude 'security-reports/' \
  --exclude '.tools/' \
  --exclude 'mobile/ios/.swiftpm/' \
  --exclude 'mobile/ios/.build/' \
  --exclude 'mobile/ios/App/.derivedData/' \
  --exclude '**/xcuserdata/' \
  --exclude 'mobile/android/.gradle/' \
  --exclude 'mobile/android/**/build/' \
  --exclude 'mobile/android/local.properties' \
  --exclude '.env' \
  --exclude '.DS_Store' \
  --exclude '.cursor/' \
  "$ROOT/" "$REMOTE:$REMOTE_DIR/"

ssh -o BatchMode=yes -o ConnectTimeout=10 "$REMOTE" bash -s <<EOF
set -euo pipefail
cd "$REMOTE_DIR"
export ANDROID_HOME="\${ANDROID_HOME:-\$HOME/Android/Sdk}"
export ANDROID_SDK_ROOT="\$ANDROID_HOME"
export PATH="\$ANDROID_HOME/cmdline-tools/latest/bin:\$ANDROID_HOME/platform-tools:\$ANDROID_HOME/emulator:\$PATH"
export JAVA_HOME="\${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
export PARALLEL_JOBS="\${PARALLEL_JOBS:-\$(nproc)}"
NPROC=\$(nproc)
export GRADLE_OPTS="\${GRADLE_OPTS:--Dorg.gradle.daemon=true -Dorg.gradle.parallel=true -Dorg.gradle.workers.max=\${NPROC}}"

if [[ ! -f .env ]]; then
  cp -n .env.example .env 2>/dev/null || cp -n .env.prod.example .env 2>/dev/null || true
fi
python3 - <<'PY'
from pathlib import Path
p = Path(".env")
if not p.exists():
    p.write_text("")
text = p.read_text()
wanted = {
    "POSTGRES_DB": "orchestra_db",
    "POSTGRES_USER": "orchestra_user",
    "POSTGRES_PASSWORD": "orchestra_pass",
    "DATABASE_URL": "postgresql://orchestra_user:orchestra_pass@db:5432/orchestra_db",
    "REDIS_URL": "redis://redis:6379/0",
}
lines, seen = [], set()
for line in text.splitlines():
    if not line or line.lstrip().startswith("#") or "=" not in line:
        lines.append(line); continue
    k = line.split("=", 1)[0].strip()
    if k in wanted:
        lines.append(f"{k}={wanted[k]}"); seen.add(k)
    else:
        lines.append(line)
for k, v in wanted.items():
    if k not in seen:
        lines.append(f"{k}={v}")
p.write_text("\\n".join(lines) + "\\n")
PY

sec_pid=""
and_pid=""
sec_code=0
and_code=0
PIPELINE_STAGE="$PIPELINE_STAGE"

if [[ "$SKIP_SECURITY" != "1" ]]; then
  echo "==> security pipeline stage=\$PIPELINE_STAGE PARALLEL_JOBS=\$PARALLEL_JOBS"
  (
    set +e
    if [[ "\$PIPELINE_STAGE" == "all" ]]; then
      docker compose down --remove-orphans >/dev/null 2>&1 || true
      docker volume rm portal_abda_postgres_data >/dev/null 2>&1 || true
    fi
    bash scripts/security/pipeline.sh "\$PIPELINE_STAGE"
    echo \$? > /tmp/portal-sec.exit
  ) > /tmp/portal-sec.log 2>&1 &
  sec_pid=\$!
fi

if [[ "$SKIP_ANDROID" != "1" ]]; then
  echo "==> Android tests + assembleDevDebug (∥ security)"
  (
    set +e
    cd mobile/android
    printf 'sdk.dir=%s\n' "\$ANDROID_HOME" > local.properties
    ./gradlew --parallel --build-cache \
      :portal-api:test :app:testDevDebugUnitTest :app:assembleDevDebug
    echo \$? > /tmp/portal-android.exit
  ) > /tmp/portal-android.log 2>&1 &
  and_pid=\$!
fi

if [[ -n "\$sec_pid" ]]; then wait "\$sec_pid" || true; fi
if [[ -n "\$and_pid" ]]; then wait "\$and_pid" || true; fi

if [[ -n "\$sec_pid" ]]; then
  sec_code=\$(cat /tmp/portal-sec.exit 2>/dev/null || echo 1)
  echo "---- security log (tail) ----"
  tail -40 /tmp/portal-sec.log || true
  echo "security exit=\$sec_code"
fi
if [[ -n "\$and_pid" ]]; then
  and_code=\$(cat /tmp/portal-android.exit 2>/dev/null || echo 1)
  echo "---- android log (tail) ----"
  tail -40 /tmp/portal-android.log || true
  echo "android exit=\$and_code"
fi

if [[ "\$sec_code" -ne 0 || "\$and_code" -ne 0 ]]; then
  echo "remote-verify FAILED (security=\$sec_code android=\$and_code)" >&2
  exit 1
fi
echo "==> remote-verify OK (mode=$VERIFY_MODE)"
EOF
