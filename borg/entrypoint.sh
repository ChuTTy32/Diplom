#!/bin/bash
# =============================================================================
# borg-клиент — поднимает WireGuard-туннель до borg-server и запускает backup.py.
# Весь трафик резервного копирования идёт по туннелю (10.8.0.0/24): репозиторий
# на borg-server доступен ТОЛЬКО через VPN.
# =============================================================================
set -e

SECRETS=/secrets
CLIENT_WG_IP=10.8.0.2
SERVER_WG_IP=10.8.0.1

mkdir -p /etc/wireguard /root/.ssh

# Ждём, пока borg-server сгенерирует ключи в общий volume
echo "[borg] waiting for borg-server secrets..."
for i in $(seq 1 60); do [ -f "$SECRETS/ready" ] && break; sleep 1; done
if [ ! -f "$SECRETS/ready" ]; then
    echo "[borg] ERROR: secrets not ready after 60s"; exit 1
fi

# ── WireGuard клиент ─────────────────────────────────────────────────
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address    = ${CLIENT_WG_IP}/24
PrivateKey = $(cat "$SECRETS/wg_client.key")

[Peer]
PublicKey           = $(cat "$SECRETS/wg_server.pub")
Endpoint            = borgserver:51820
AllowedIPs          = ${SERVER_WG_IP}/32
PersistentKeepalive = 25
EOF
wg-quick up wg0
echo "[borg] WireGuard wg0 up (${CLIENT_WG_IP}) → peer ${SERVER_WG_IP}"

# ── SSH-ключ клиента ─────────────────────────────────────────────────
cp "$SECRETS/borg_client_id" /root/.ssh/id_borg
chmod 600 /root/.ssh/id_borg

# borg по ssh через туннель; ключ хоста не проверяем (демо, ephemeral-узел)
export BORG_RSH="ssh -i /root/.ssh/id_borg -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"

exec python3 backup.py
