#!/usr/bin/env bash
# No Ubuntu: sobe API (compose), garante emulador, instala APK e abre o app.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

cd "$ROOT"
if ! docker info >/dev/null 2>&1; then
  echo "Docker necessário no Ubuntu para a API." >&2
  exit 1
fi
docker compose up -d --build
# wait health
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1 || curl -sf http://127.0.0.1:8000/docs >/dev/null 2>&1; then
    echo "API up"
    break
  fi
  sleep 2
done

cd "$ROOT/mobile/android"
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > local.properties
./gradlew --no-daemon :app:assembleDevDebug

if ! adb devices | grep -q emulator; then
  nohup emulator -avd Portal_API35 -no-audio -no-window -no-boot-anim -gpu swiftshader_indirect \
    >/tmp/portal-emulator.log 2>&1 &
fi
adb wait-for-device
for i in $(seq 1 60); do
  [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]] && break
  sleep 3
done

adb install -r app/build/outputs/apk/dev/debug/app-dev-debug.apk
adb shell am start -n org.orchestra.portal.membro.dev/org.orchestra.portal.membro.MainActivity
echo "Smoke: app launched. Login musico / musico123"
