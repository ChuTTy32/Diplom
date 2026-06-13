#!/bin/bash
# =============================================================================
# borg-server — изолированный узел хранения (настоящий серверный WORM).
#
# Запускает:
#   1) WireGuard wg0 (10.8.0.1) — туннель до borg-клиента;
#   2) sshd, слушающий ТОЛЬКО на адресе туннеля 10.8.0.1 — репозиторий
#      недоступен иначе как через VPN (Zero Trust);
#   3) forced-command `borg serve --append-only` — клиент физически не может
#      выполнить delete/prune/compact: append-only навязан СЕРВЕРОМ, а не
#      клиентской конфигурацией. Это и есть настоящая иммутабельность.
#
# Ключи (WG обеих сторон + SSH клиента) генерируются один раз в общий volume
# /secrets — borg-клиент забирает оттуда свои приватные ключи.
# =============================================================================
set -e

SECRETS=/secrets
SERVER_WG_IP=10.8.0.1
CLIENT_WG_IP=10.8.0.2
WG_PORT=51820

mkdir -p "$SECRETS" /repo /run/sshd /root/.ssh

# ── Однократная генерация ключей ─────────────────────────────────────
if [ ! -f "$SECRETS/ready" ]; then
    echo "[borg-server] generating WG + SSH keys..."
    wg genkey | tee "$SECRETS/wg_server.key" | wg pubkey > "$SECRETS/wg_server.pub"
    wg genkey | tee "$SECRETS/wg_client.key" | wg pubkey > "$SECRETS/wg_client.pub"
    ssh-keygen -t ed25519 -N "" -f "$SECRETS/borg_client_id" -q
    chmod 600 "$SECRETS"/wg_*.key "$SECRETS/borg_client_id"
    touch "$SECRETS/ready"
fi

# ── WireGuard ────────────────────────────────────────────────────────
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address    = ${SERVER_WG_IP}/24
ListenPort = ${WG_PORT}
PrivateKey = $(cat "$SECRETS/wg_server.key")

[Peer]
PublicKey  = $(cat "$SECRETS/wg_client.pub")
AllowedIPs = ${CLIENT_WG_IP}/32
EOF
wg-quick up wg0
echo "[borg-server] WireGuard wg0 up (${SERVER_WG_IP})"

# ── SSH: forced borg serve --append-only ─────────────────────────────
cat > /root/.ssh/authorized_keys <<EOF
command="borg serve --append-only --restrict-to-repository /repo",restrict,no-port-forwarding,no-X11-forwarding $(cat "$SECRETS/borg_client_id.pub")
EOF
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys

ssh-keygen -A
# sshd слушает ТОЛЬКО на адресе туннеля — репозиторий доступен лишь через VPN
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin forced-commands-only/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
echo "ListenAddress ${SERVER_WG_IP}" >> /etc/ssh/sshd_config

echo "[borg-server] sshd on ${SERVER_WG_IP}:22 — borg serve --append-only (server-enforced WORM)"
exec /usr/sbin/sshd -D -e
