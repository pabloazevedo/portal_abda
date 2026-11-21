#!/usr/bin/env bash
# Instala hooks que disparam a esteira no Ubuntu (sem alterar git config).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cp "$ROOT/.githooks/pre-commit" "$ROOT/.git/hooks/pre-commit"
cp "$ROOT/.githooks/pre-push" "$ROOT/.git/hooks/pre-push"
chmod +x "$ROOT/.git/hooks/pre-commit" "$ROOT/.git/hooks/pre-push"
echo "Hooks: pre-commit=fast (~1min) | pre-push=full (image+DAST)"
