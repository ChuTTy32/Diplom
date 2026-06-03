#!/bin/bash
# =============================================================================
# Генерация WireGuard ключей для всех узлов системы
# Запускать ОДИН РАЗ перед первым деплоем
# Результат: заполненные конфиги в wireguard/config/
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/../config"

mkdir -p "$CONFIG_DIR"

# Проверяем наличие wg
if ! command -v wg &>/dev/null; then
    echo "WireGuard не установлен. Устанавливаем..."
    apt-get update -qq && apt-get install -y -qq wireguard-tools
fi

echo "=== Генерация ключей WireGuard ==="
echo ""

# ─── Генерируем ключевые пары ────────────────────────────────────────
for NODE in server agent borg; do
    PRIV="$CONFIG_DIR/${NODE}_private.key"
    PUB="$CONFIG_DIR/${NODE}_public.key"
    
    wg genkey | tee "$PRIV" | wg pubkey > "$PUB"
    chmod 600 "$PRIV"
    echo "[$NODE]"
    echo "  Private: $(cat $PRIV)"
    echo "  Public:  $(cat $PUB)"
    echo ""
done

# ─── Читаем ключи ────────────────────────────────────────────────────
SERVER_PRIV=$(cat "$CONFIG_DIR/server_private.key")
SERVER_PUB=$(cat "$CONFIG_DIR/server_public.key")
AGENT_PRIV=$(cat "$CONFIG_DIR/agent_private.key")
AGENT_PUB=$(cat "$CONFIG_DIR/agent_public.key")
BORG_PRIV=$(cat "$CONFIG_DIR/borg_private.key")
BORG_PUB=$(cat "$CONFIG_DIR/borg_public.key")

# ─── SERVER конфиг (backend) ─────────────────────────────────────────
cat > "$CONFIG_DIR/wg1.conf" << EOF
# WireGuard Server (Backend/API Gateway)
# IP в туннеле: 172.21.0.1
# Принимает подключения от агента и борга

[Interface]
Address    = 172.21.0.1/24
ListenPort = 51820
PrivateKey = ${SERVER_PRIV}

# Разрешаем форвардинг через туннель
PostUp   = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

# ─── Peer: Agent ───────────────────────────────────────────────────
[Peer]
# Хостовый агент мониторинга
PublicKey  = ${AGENT_PUB}
AllowedIPs = 172.21.0.2/32

# ─── Peer: Borg ────────────────────────────────────────────────────
[Peer]
# BorgBackup сервис
PublicKey  = ${BORG_PUB}
AllowedIPs = 172.21.0.3/32
EOF

# ─── AGENT конфиг ────────────────────────────────────────────────────
cat > "$CONFIG_DIR/wg0-agent.conf" << EOF
# WireGuard Agent (мониторинг файловой системы)
# IP в туннеле: 172.21.0.2
# Подключается к серверу, трафик метрик только через VPN

[Interface]
Address    = 172.21.0.2/24
PrivateKey = ${AGENT_PRIV}
# DNS внутри туннеля
DNS        = 172.21.0.1

[Peer]
# Backend/API Gateway
PublicKey  = ${SERVER_PUB}
Endpoint   = backend:51820
# Только трафик к API через туннель (не весь трафик)
AllowedIPs = 172.21.0.0/24
# Keepalive для поддержания соединения
PersistentKeepalive = 25
EOF

# ─── BORG конфиг ─────────────────────────────────────────────────────
cat > "$CONFIG_DIR/wg0-borg.conf" << EOF
# WireGuard Borg (резервное копирование)
# IP в туннеле: 172.21.0.3
# Весь трафик бэкапов только через VPN — Zero Trust

[Interface]
Address    = 172.21.0.3/24
PrivateKey = ${BORG_PRIV}
DNS        = 172.21.0.1

[Peer]
# Backend/API Gateway
PublicKey  = ${SERVER_PUB}
Endpoint   = backend:51820
AllowedIPs = 172.21.0.0/24
PersistentKeepalive = 25
EOF

chmod 600 "$CONFIG_DIR"/*.conf

echo "=== Конфиги созданы ==="
echo ""
echo "  $CONFIG_DIR/wg1.conf  → монтировать в /etc/wireguard/ контейнера backend"
echo "  $CONFIG_DIR/wg0-agent.conf   → монтировать в /etc/wireguard/ контейнера agent"
echo "  $CONFIG_DIR/wg0-borg.conf    → монтировать в /etc/wireguard/ контейнера borg"
echo ""
echo "ВАЖНО: приватные ключи хранятся только в $CONFIG_DIR/"
echo "       не коммитить в git!"
