#!/usr/bin/env bash
# Libera espaço no Mac: prune Docker e encerra Docker/OrbStack.
# Mac fica só para edição de código; build/teste = Ubuntu 192.168.50.32.
set -euo pipefail

open -a OrbStack 2>/dev/null || open -a Docker 2>/dev/null || true
for i in $(seq 1 30); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done

if docker info >/dev/null 2>&1; then
  docker system prune -af --volumes
  docker builder prune -af 2>/dev/null || true
  docker system df || true
else
  echo "Docker indisponível; nada a limpar."
fi

osascript -e 'quit app "OrbStack"' 2>/dev/null || true
osascript -e 'quit app "Docker"' 2>/dev/null || true
osascript -e 'quit app "Docker Desktop"' 2>/dev/null || true
echo "Mac coding-only: Docker encerrado."
