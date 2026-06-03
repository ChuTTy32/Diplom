#!/bin/bash

WG_IFACE="wg1"
CONFIG="/etc/wireguard/${WG_IFACE}.conf"

# Fallback: wg0.conf → wg1.conf
if [ ! -f "$CONFIG" ] && [ -f "/etc/wireguard/wg0.conf" ]; then
    cp /etc/wireguard/wg0.conf "$CONFIG"
fi

if [ ! -f "$CONFIG" ]; then
    echo "[WireGuard] Config $CONFIG not found. Run: sudo bash wireguard/scripts/gen_keys.sh"
    sleep infinity
    exit 0
fi

# ip_forward — пробуем, но не падаем если read-only (уже включён на хосте)
sysctl -w net.ipv4.ip_forward=1 2>/dev/null && \
    echo "[WireGuard] ip_forward enabled" || \
    echo "[WireGuard] ip_forward already set by host (ok)"

echo "[WireGuard] Starting interface ${WG_IFACE}..."

# wg-quick требует имя интерфейса совпадающее с именем файла
wg-quick up ${WG_IFACE}

if [ $? -eq 0 ]; then
    echo "[WireGuard] ✓ Interface ${WG_IFACE} is UP"
    wg show
else
    echo "[WireGuard] ✗ Failed to bring up ${WG_IFACE}"
    exit 1
fi

# Держим контейнер живым
while true; do
    sleep 60
    PEERS=$(wg show ${WG_IFACE} peers 2>/dev/null | wc -l || echo "?")
    echo "[WireGuard] $(date +%T) peers=${PEERS}"
done
