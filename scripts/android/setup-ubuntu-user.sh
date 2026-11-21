#!/usr/bin/env bash
# Instalação sem sudo: JDK já no sistema + Android SDK no $HOME.
# Uso no Ubuntu: bash scripts/android/setup-ubuntu-user.sh
set -euo pipefail

ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
CMDLINE_VERSION="${CMDLINE_VERSION:-11076708}"
API_LEVEL="${API_LEVEL:-35}"
BUILD_TOOLS="${BUILD_TOOLS:-35.0.0}"
SYSTEM_IMAGE="${SYSTEM_IMAGE:-system-images;android-${API_LEVEL};google_apis;x86_64}"
AVD_NAME="${AVD_NAME:-Portal_API35}"

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
mv /tmp/cmdline-tools-extract/cmdline-tools/* "$ANDROID_HOME/cmdline-tools/latest/"

export ANDROID_HOME ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

echo "==> Licenças + pacotes SDK"
mkdir -p "$ANDROID_HOME/licenses"
cat > "$ANDROID_HOME/licenses/android-sdk-license" <<'EOF'
24333f8a63b6825ea9c5514f83c2829b004d1fee
EOF
cat > "$ANDROID_HOME/licenses/android-sdk-preview-license" <<'EOF'
84831b9409646a918e30573bab4c9c91346d8abd
EOF
yes | sdkmanager --licenses >/tmp/android-licenses.log 2>&1 || true
sdkmanager --install \
  "platform-tools" \
  "platforms;android-${API_LEVEL}" \
  "build-tools;${BUILD_TOOLS}" \
  "emulator" \
  "$SYSTEM_IMAGE"

echo "==> AVD $AVD_NAME"
if ! avdmanager list avd 2>/dev/null | grep -q "$AVD_NAME"; then
  echo "no" | avdmanager create avd -n "$AVD_NAME" -k "$SYSTEM_IMAGE" --device "pixel_6" --force
fi

PROFILE="$HOME/.bashrc"
MARKER="# portal-android-sdk"
if ! grep -q "$MARKER" "$PROFILE" 2>/dev/null; then
  cat >> "$PROFILE" <<EOF

$MARKER
export ANDROID_HOME="$ANDROID_HOME"
export ANDROID_SDK_ROOT="\$ANDROID_HOME"
export PATH="\$ANDROID_HOME/cmdline-tools/latest/bin:\$ANDROID_HOME/platform-tools:\$ANDROID_HOME/emulator:\$PATH"
EOF
fi

echo "✅ SDK em $ANDROID_HOME — AVD $AVD_NAME"
echo "Nota: se o emulador falhar em /dev/kvm, rode no console: sudo usermod -aG kvm \$USER && newgrp kvm"
