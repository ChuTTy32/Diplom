#!/bin/bash
# Симуляция ransomware-атаки для демо комиссии
# Использование:
#   bash simulate_attack.sh          # стандартный темп (2 сек между файлами)
#   bash simulate_attack.sh --fast   # быстро (0.5 сек), для повторных прогонов

set -euo pipefail

WATCH_DIR="${WATCH_PATH:-/tmp/monitored}"
BACKEND="http://localhost:8000"
DELAY=2
[ "${1:-}" = "--fast" ] && DELAY=0.5

RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'
CYN='\033[0;36m'; DIM='\033[2m'; NC='\033[0m'

log()  { echo -e "${DIM}[$(date +%T)]${NC} $*"; }
ok()   { echo -e "${GRN}  ✓ $*${NC}"; }
warn() { echo -e "${YEL}  ⚠ $*${NC}"; }
err()  { echo -e "${RED}  ✗ $*${NC}"; }

echo -e "${CYN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║     RANSOMWARE ATTACK SIMULATION v2.0        ║"
echo "  ║     RansomGuard Detection Demo               ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Проверяем доступность бэкенда ─────────────────────────────────────
if ! curl -sf "$BACKEND/health" > /dev/null 2>&1; then
    err "Backend недоступен: $BACKEND"
    err "Запустите: docker compose up -d && docker compose ps"
    exit 1
fi
ok "Backend online: $BACKEND"

# ── Ждём агента: метрики идут = watchdog/eBPF готовы ──────────────────
# После рестарта агент компилирует BPF ~20с — атака в этот период
# пройдёт мимо детекции. Свежая system-метрика = агент жив.
log "Waiting for agent (system metrics)..."
AGENT_UP=0
for _ in $(seq 1 20); do
    CNT=$(curl -sf "$BACKEND/metrics/system?minutes=1" \
        | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
    if [ "${CNT:-0}" -gt 0 ]; then AGENT_UP=1; break; fi
    sleep 2
done
if [ "$AGENT_UP" = 1 ]; then
    ok "Agent online (metrics flowing)"
else
    warn "Агент не прислал метрик за 40с — детекция может не сработать"
    warn "  Проверьте: docker compose logs agent --tail=20"
fi

# ── Фиксируем baseline до симуляции ───────────────────────────────────
BEFORE=$(curl -sf "$BACKEND/incidents/list?limit=500" \
    | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
log "Baseline incidents: $BEFORE"

# ── Сброс lockdown и подготовка директории ────────────────────────────
echo ""
log "Resetting lockdown + preparing directory..."
curl -sf -X POST "$BACKEND/incidents/reset-lockdown" > /dev/null
# Восстанавливаем права если lockdown успел сработать в прошлый раз
chmod -R 755 "$WATCH_DIR" 2>/dev/null || true
# Удаляем артефакты прошлых прогонов — старые .locked/.enc заново
# триггерят алерты при первом скане после рестарта агента
rm -rf "$WATCH_DIR/documents"
mkdir -p "$WATCH_DIR/documents"
ok "Ready. watch_dir=$WATCH_DIR (старые демо-файлы удалены)"
sleep 1

# ── ФАЗА 1: нормальные файлы (низкая энтропия) ────────────────────────
echo ""
echo -e "${GRN}▶ PHASE 1 — Normal files (H ≈ 3–5 bits)${NC}"
echo "This is a normal text document."            > "$WATCH_DIR/documents/report.txt"
echo "SELECT * FROM users WHERE active = 1;"      > "$WATCH_DIR/documents/query.sql"
echo '{"version":1,"name":"config","debug":false}' > "$WATCH_DIR/documents/config.json"
WATCH_DIR="$WATCH_DIR" python3 -c "
import os, random, string
data = ''.join(random.choices(string.ascii_letters + string.digits + ' \n', k=4096))
path = os.path.join(os.environ['WATCH_DIR'], 'documents', 'source_code.py')
open(path, 'w').write(data)
" 2>/dev/null || true
ok "4 нормальных файла — дашборд должен показать H < 7.0"
sleep "$DELAY"

# ── ФАЗА 2: одиночные зашифрованные файлы (детекция агентом) ──────────
echo ""
echo -e "${YEL}▶ PHASE 2 — Ransomware encrypting files (H ≈ 8.0)${NC}"
warn "Watch dashboard → entropy spikes: http://localhost:3000"
echo ""

for i in {1..6}; do
    SIZE=$((32 + RANDOM % 96))
    FILE="$WATCH_DIR/documents/encrypted_${i}.locked"
    dd if=/dev/urandom of="$FILE" bs=1024 count="$SIZE" 2>/dev/null
    log "${RED}encrypted_${i}.locked${NC} ${DIM}(${SIZE} KB, H≈8.0)${NC}"
    sleep "$DELAY"
done
ok "6 зашифрованных файлов. Агент должен зарегистрировать алерты (H > 7.2)"

# ── ФАЗА 3: массовое шифрование — триггер lockdown ────────────────────
echo ""
echo -e "${RED}▶ PHASE 3 — Mass encryption → LOCKDOWN TRIGGER${NC}"
warn "Ожидается: ≥3 алертов за 30 сек → emergency_backup или lockdown"
echo ""

for i in {1..6}; do
    FILE="$WATCH_DIR/documents/RANSOM_${i}.enc"
    if ! dd if=/dev/urandom of="$FILE" bs=1024 count=64 2>/dev/null; then
        warn "Не могу записать RANSOM_${i}.enc — вероятно lockdown уже сработал"
        warn "Это ожидаемое поведение: директория переведена в read-only"
        break
    fi
    log "${RED}RANSOM_${i}.enc${NC} ${DIM}(64 KB)${NC}"
    sleep 0.8
done

# ── Ждём реакции системы ──────────────────────────────────────────────
echo ""
log "Waiting for detection pipeline (15s)..."
sleep 15

# ── Итоги ─────────────────────────────────────────────────────────────
TOTAL=$(curl -sf "$BACKEND/incidents/list?limit=500" \
    | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
NEW=$((TOTAL - BEFORE))

LATEST=$(curl -sf "$BACKEND/incidents/list?limit=3" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if d:
    for r in d:
        print(f\"    {r['action_taken'].upper():18s} entropy={r['entropy']:.4f}  {r['time'][11:19]}\")
else:
    print('    no incidents yet')
" 2>/dev/null || echo "    parse error")

ALERT_COUNT=$(curl -sf "$BACKEND/metrics/entropy?minutes=5&alert_only=true" \
    | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")

echo ""
echo -e "${CYN}══════════════════════════════════════════════════${NC}"
echo -e "${CYN}  РЕЗУЛЬТАТЫ СИМУЛЯЦИИ${NC}"
echo -e "${CYN}══════════════════════════════════════════════════${NC}"
echo -e "  Entropy alerts (last 5m) : ${RED}$ALERT_COUNT${NC}"
echo -e "  New incidents this run   : ${RED}+$NEW${NC} (total: $TOTAL)"
echo -e "  Actions (latest 3):"
echo -e "${RED}$LATEST${NC}"
echo ""
echo -e "  Dashboard  → ${CYN}http://localhost:3000${NC}"
echo -e "  Incidents  → ${CYN}curl $BACKEND/incidents/list | python3 -m json.tool${NC}"
echo -e "  Audit log  → ${CYN}curl $BACKEND/incidents/audit | python3 -m json.tool${NC}"
echo -e "${CYN}══════════════════════════════════════════════════${NC}"
echo ""

if [ "$NEW" -gt 0 ] 2>/dev/null; then
    ok "Система обнаружила атаку и зафиксировала $NEW инцидент(ов)"
else
    warn "Инциденты не зафиксированы — проверьте логи агента:"
    warn "  docker compose logs agent --tail=50"
fi
