#!/usr/bin/env bash
# Sincroniza o repo para o Ubuntu de build e roda esteira + testes Android lá.
# Mac = só código. Host: 192.168.50.32 (ub2404202405).
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-192.168.50.32}"
REMOTE_USER="${REMOTE_USER:-pablo}"
REMOTE="${REMOTE_USER}@${REMOTE_HOST}"
REMOTE_DIR="${REMOTE_DIR:-/home/pablo/git/portal_abda}"
ROOT="$(git rev-parse --show-toplevel)"
SKIP_SECURITY="${SKIP_SECURITY:-0}"
SKIP_ANDROID="${SKIP_ANDROID:-0}"

echo "==> rsync → $REMOTE:$REMOTE_DIR"
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

# Compose local stack: alinhar credenciais padrão (volume pode ter sido criado com outra senha).
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

if [[ "$SKIP_SECURITY" != "1" ]]; then
  echo "==> security pipeline (Ubuntu)"
  # Volume Postgres antigo com senha diferente quebra /healthz no DAST.
  docker compose down --remove-orphans >/dev/null 2>&1 || true
  docker volume rm portal_abda_postgres_data >/dev/null 2>&1 || true
  bash scripts/security/pipeline.sh all
fi

if [[ "$SKIP_ANDROID" != "1" ]]; then
  echo "==> Android unit tests + assembleDevDebug"
  cd mobile/android
  printf 'sdk.dir=%s\n' "\$ANDROID_HOME" > local.properties
  ./gradlew --no-daemon :portal-api:test :app:testDevDebugUnitTest :app:assembleDevDebug
fi
echo "==> remote-verify OK"
EOF
