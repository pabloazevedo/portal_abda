#!/usr/bin/env bash
# Instala JDK 17 + Android SDK cmdline-tools + plataforma + emulador no Ubuntu.
# Uso (no host 192.168.50.32, como usuário pablo):
#   bash scripts/android/setup-ubuntu.sh
set -euo pipefail

ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
CMDLINE_VERSION="${CMDLINE_VERSION:-11076708}"
API_LEVEL="${API_LEVEL:-35}"
BUILD_TOOLS="${BUILD_TOOLS:-35.0.0}"
SYSTEM_IMAGE="${SYSTEM_IMAGE:-system-images;android-${API_LEVEL};google_apis;x86_64}"
AVD_NAME="${AVD_NAME:-Portal_API35}"

echo "==> Pacotes do sistema"
sudo apt-get update
sudo apt-get install -y \
  openjdk-17-jdk \
  unzip \
  curl \
  wget \
  git \
  libnss3 \
  libx11-6 \
  libpulse0 \
  libgl1 \
  cpu-checker \
  qemu-kvm \
  libvirt-daemon-system \
  bridge-utils

echo "==> ANDROID_HOME=$ANDROID_HOME"
mkdir -p "$ANDROID_HOME/cmdline-tools"
cd /tmp
ZIP="commandlinetools-linux-${CMDLINE_VERSION}_latest.zip"
if [[ ! -f "$ZIP" ]]; then
  wget -q "https://dl.google.com/android/repository/${ZIP}"
fi
rm -rf /tmp/cmdline-tools-extract
unzip -q -o "$ZIP" -d /tmp/cmdline-tools-extract
rm -rf "$ANDROID_HOME/cmdline-tools/latest"
mkdir -p "$ANDROID_HOME/cmdline-tools/latest"
# O zip traz pasta "cmdline-tools/"; movemos o conteúdo para latest/
mv /tmp/cmdline-tools-extract/cmdline-tools/* "$ANDROID_HOME/cmdline-tools/latest/"

export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

echo "==> Aceitar licenças e instalar pacotes SDK"
yes | sdkmanager --licenses >/tmp/android-licenses.log || true
sdkmanager --install \
  "platform-tools" \
  "platforms;android-${API_LEVEL}" \
  "build-tools;${BUILD_TOOLS}" \
  "emulator" \
  "$SYSTEM_IMAGE"

echo "==> Grupo kvm (reinicie a sessão se acabou de ser adicionado)"
if getent group kvm >/dev/null; then
  sudo usermod -aG kvm "$USER" || true
fi

echo "==> AVD $AVD_NAME"
if ! avdmanager list avd | grep -q "$AVD_NAME"; then
  echo "no" | avdmanager create avd -n "$AVD_NAME" -k "$SYSTEM_IMAGE" --device "pixel_6" --force
fi

PROFILE="$HOME/.bashrc"
MARKER="# portal-android-sdk"
if ! grep -q "$MARKER" "$PROFILE" 2>/dev/null; then
  cat >> "$PROFILE" <<EOF

$MARKER
export ANDROID_HOME=\"$ANDROID_HOME\"
export ANDROID_SDK_ROOT=\"\$ANDROID_HOME\"
export PATH=\"\$ANDROID_HOME/cmdline-tools/latest/bin:\$ANDROID_HOME/platform-tools:\$ANDROID_HOME/emulator:\$PATH\"
EOF
fi

cat <<EOF

✅ SDK pronto em $ANDROID_HOME
Próximos passos:
  source ~/.bashrc
  cd /caminho/do/portal_abda/mobile/android
  cp local.properties.example local.properties
  # ajuste sdk.dir se necessário
  ./gradlew :app:assembleDevDebug
  emulator -avd $AVD_NAME -no-audio -no-boot-anim &
  adb wait-for-device
  adb install -r app/build/outputs/apk/dev/debug/app-dev-debug.apk

KVM: rode 'kvm-ok'. Se falhar, habilite virtualização no BIOS / nest nested.
EOF
