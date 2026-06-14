#!/bin/bash
# =============================================================================
# RansomGuard — первоначальная установка окружения
#
# Что делает:
#   1. Проверяет зависимости (Docker, Compose, Python3, curl)
#   2. Создаёт .env с безопасными секретами (если не существует)
#   3. Создаёт нужные директории
#   4. Собирает образы и запускает сервисы
#   5. Ждёт healthcheck и показывает статус
#
# Что НЕ делает: не трогает исходный код.
#
# Использование:
#   bash setup.sh            # полная установка
#   bash setup.sh --no-start # только окружение, без запуска Docker
# =============================================================================

set -euo pipefail

NO_START=false
[ "${1:-}" = "--no-start" ] && NO_START=true

# ── Цвета ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'
CYN='\033[0;36m'; DIM='\033[2m'; NC='\033[0m'

STEP=0
step() { STEP=$((STEP+1)); echo -e "\n${CYN}[${STEP}]${NC} $*"; }
ok()   { echo -e "    ${GRN}✓${NC} $*"; }
warn() { echo -e "    ${YEL}⚠${NC} $*"; }
die()  { echo -e "\n${RED}ОШИБКА:${NC} $*\n" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║     RansomGuard — Setup v2.0                 ║"
echo "  ║     НГАСУ (Сибстрин) · ВКР 09.03.02         ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ═══════════════════════════════════════════════════════════════════════
# ШАГ 1 — ПРОВЕРКА ЗАВИСИМОСТЕЙ
# ═══════════════════════════════════════════════════════════════════════
step "Проверка зависимостей"

# Docker
if ! command -v docker &>/dev/null; then
    die "Docker не найден. Установите: https://docs.docker.com/engine/install/"
fi
DOCKER_VER=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "0.0")
DOCKER_MAJOR=$(echo "$DOCKER_VER" | cut -d. -f1)
if [ "$DOCKER_MAJOR" -lt 24 ] 2>/dev/null; then
    warn "Docker $DOCKER_VER — рекомендуется ≥24. Обновите при проблемах."
else
    ok "Docker $DOCKER_VER"
fi

# Docker Compose v2
if ! docker compose version &>/dev/null; then
    die "Docker Compose v2 не найден. Установите плагин: apt-get install docker-compose-plugin"
fi
COMPOSE_VER=$(docker compose version --short 2>/dev/null || echo "?")
ok "Docker Compose v$COMPOSE_VER"

# Права на Docker без sudo
if ! docker info &>/dev/null; then
    warn "Docker требует sudo. Добавьте пользователя в группу docker:"
    warn "  sudo usermod -aG docker \$USER && newgrp docker"
    DOCKER_CMD="sudo docker"
else
    DOCKER_CMD="docker"
    ok "Docker без sudo"
fi

# Python3
if ! command -v python3 &>/dev/null; then
    die "python3 не найден. Установите: apt-get install python3"
fi
ok "Python $(python3 --version 2>&1 | cut -d' ' -f2)"

# curl
if ! command -v curl &>/dev/null; then
    die "curl не найден. Установите: apt-get install curl"
fi
ok "curl $(curl --version | head -1 | cut -d' ' -f2)"

# ═══════════════════════════════════════════════════════════════════════
# ШАГ 2 — ФАЙЛ КОНФИГУРАЦИИ .env
# ═══════════════════════════════════════════════════════════════════════
step "Конфигурация .env"

if [ -f ".env" ]; then
    ok ".env уже существует — не перезаписываем"
else
    warn ".env не найден — создаём с безопасными секретами"
    # Генерируем случайные секреты через openssl
    PG_PASS=$(openssl rand -hex 16)
    BORG_PASS=$(openssl rand -hex 24)
    SECRET_KEY=$(openssl rand -hex 32)
    RG_TOKEN=$(openssl rand -hex 32)
    cat > .env << EOF
# PostgreSQL / TimescaleDB
POSTGRES_USER=admin
POSTGRES_PASSWORD=${PG_PASS}
POSTGRES_DB=metrics

# BorgBackup
BORG_PASSPHRASE=${BORG_PASS}

# Agent
WATCH_PATH=/tmp/monitored
ENTROPY_THRESHOLD=7.2
SCAN_INTERVAL=5

# Backend
SECRET_KEY=${SECRET_KEY}
DEBUG=false

# Bearer-токен для аутентификации машина-машина (агент/borg → backend)
RG_TOKEN=${RG_TOKEN}

# BorgBackup restore speed estimate (MB/s)
RESTORE_SPEED_MB_PER_SEC=100.0
EOF
    ok ".env создан (секреты сгенерированы через openssl)"
fi

# Читаем WATCH_PATH из .env
WATCH_PATH=$(grep '^WATCH_PATH=' .env | cut -d= -f2 | tr -d '"' | tr -d "'")
WATCH_PATH="${WATCH_PATH:-/tmp/monitored}"

# ═══════════════════════════════════════════════════════════════════════
# ШАГ 3 — ДИРЕКТОРИИ
# ═══════════════════════════════════════════════════════════════════════
step "Создание директорий"

mkdir -p "$WATCH_PATH"
ok "WATCH_PATH: $WATCH_PATH"

# Каталог мог остаться от прошлого `docker compose up` во владении root
# (Docker создаёт точку bind-mount как root). Тогда симуляция атаки, которая
# пишет от текущего пользователя, падает на mkdir: Permission denied.
# Приводим владельца к текущему пользователю.
CUR_USER=$(id -un)
if [ "$(stat -c '%U' "$WATCH_PATH" 2>/dev/null)" != "$CUR_USER" ]; then
    if chown -R "$CUR_USER:$CUR_USER" "$WATCH_PATH" 2>/dev/null \
       || sudo chown -R "$CUR_USER:$CUR_USER" "$WATCH_PATH" 2>/dev/null; then
        ok "Владелец $WATCH_PATH → $CUR_USER"
    else
        warn "$WATCH_PATH принадлежит другому пользователю; смена не удалась"
        warn "  Выполните вручную: sudo chown -R $CUR_USER:$CUR_USER $WATCH_PATH"
    fi
fi

mkdir -p backend/data
ok "backend/data (SQLite аудит-лог)"

# Права на WATCH_PATH — агент должен читать/писать
chmod 755 "$WATCH_PATH"
ok "Права 755 на $WATCH_PATH"

# ═══════════════════════════════════════════════════════════════════════
# ШАГ 4 — ЗАПУСК (если не --no-start)
# ═══════════════════════════════════════════════════════════════════════
if [ "$NO_START" = true ]; then
    echo ""
    ok "Окружение готово. Для запуска: make start  или  docker compose up -d --build"
    exit 0
fi

step "Сборка и запуск Docker Compose"

$DOCKER_CMD compose build --parallel
ok "Образы собраны"

$DOCKER_CMD compose up -d
ok "Контейнеры запущены"

# ═══════════════════════════════════════════════════════════════════════
# ШАГ 5 — ОЖИДАНИЕ ГОТОВНОСТИ
# ═══════════════════════════════════════════════════════════════════════
step "Ожидание готовности сервисов"

echo -e "    ${DIM}Ждём backend healthcheck (до 60 сек)...${NC}"
TIMEOUT=60
ELAPSED=0
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo ""
        warn "Backend не ответил за ${TIMEOUT}s. Проверьте логи:"
        warn "  docker compose logs backend --tail=30"
        break
    fi
    printf "."
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
echo ""

if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    ok "Backend online (${ELAPSED}s)"
else
    warn "Backend может быть ещё не готов"
fi

# Фронтенд — ждём меньше, он стартует позже
echo -e "    ${DIM}Ждём frontend (до 30 сек)...${NC}"
ELAPSED=0
until curl -sf http://localhost:3000 > /dev/null 2>&1; do
    if [ "$ELAPSED" -ge 30 ]; then
        warn "Frontend не ответил за 30s (может стартовать дольше)"
        break
    fi
    printf "."
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
echo ""
if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    ok "Frontend online (${ELAPSED}s)"
fi

# ═══════════════════════════════════════════════════════════════════════
# ШАГ 6 — СТАТУС И ИТОГ
# ═══════════════════════════════════════════════════════════════════════
step "Статус контейнеров"
$DOCKER_CMD compose ps

echo ""
echo -e "${CYN}══════════════════════════════════════════════════${NC}"
echo -e "${CYN}  УСТАНОВКА ЗАВЕРШЕНА${NC}"
echo -e "${CYN}══════════════════════════════════════════════════${NC}"
echo -e "  Dashboard   →  ${GRN}http://localhost:3000${NC}"
echo -e "  API         →  ${GRN}http://localhost:8000${NC}"
echo -e "  Swagger UI  →  ${GRN}http://localhost:8000/docs${NC}"
echo -e "  WATCH_PATH  →  ${GRN}$WATCH_PATH${NC}"
echo ""
echo -e "  Симуляция атаки:"
echo -e "    ${DIM}bash simulate_attack.sh${NC}         # стандартный темп"
echo -e "    ${DIM}bash simulate_attack.sh --fast${NC}  # быстро"
echo -e "  Остановить:"
echo -e "    ${DIM}docker compose down${NC}"
echo -e "${CYN}══════════════════════════════════════════════════${NC}"
