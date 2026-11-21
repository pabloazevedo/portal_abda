#!/usr/bin/env bash
# Rode UMA VEZ no console físico/VNC do Ubuntu 192.168.50.32 para liberar acesso remoto.
set -euo pipefail
sudo apt-get update
sudo apt-get install -y openssh-server
sudo systemctl enable --now ssh
sudo ufw allow OpenSSH 2>/dev/null || true
echo "SSH ativo. Do Mac: ssh pablo@192.168.50.32"
ip -4 addr show | grep -E 'inet ' || true
