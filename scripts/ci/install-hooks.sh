#!/usr/bin/env bash
# Instala o pre-commit que dispara a esteira no Ubuntu (sem alterar git config).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cp "$ROOT/.githooks/pre-commit" "$ROOT/.git/hooks/pre-commit"
chmod +x "$ROOT/.git/hooks/pre-commit"
echo "Hook instalado: .git/hooks/pre-commit → remote-verify (Ubuntu)"
