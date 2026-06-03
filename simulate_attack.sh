#!/bin/bash
# Симуляция ransomware-атаки для демо комиссии
# Использование: bash simulate_attack.sh [--fast]

WATCH_DIR="/tmp/monitored"
FAST=${1:-""}
DELAY=3
[ "$FAST" = "--fast" ] && DELAY=1

RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'; CYN='\033[0;36m'; NC='\033[0m'

echo -e "${CYN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYN}║     RANSOMWARE ATTACK SIMULATION v1.0        ║${NC}"
echo -e "${CYN}║     RansomGuard Detection Demo               ║${NC}"
echo -e "${CYN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Сбрасываем lockdown на хосте напрямую
echo -e "${GRN}[INIT] Resetting lockdown...${NC}"
curl -s -X POST http://localhost:8000/incidents/reset-lockdown > /dev/null
sudo chown -R $USER:$USER "$WATCH_DIR" 2>/dev/null || true
sudo find "$WATCH_DIR" -type d -exec chmod 755 {} \;
sudo find "$WATCH_DIR" -type f -exec chmod 644 {} \;
mkdir -p "$WATCH_DIR/documents"
echo -e "${GRN}✓ Ready${NC}"
echo ""
sleep 1

# Фаза 1: нормальные файлы
echo -e "${GRN}[PHASE 1] Creating normal files (low entropy)...${NC}"
echo "Normal text document." > "$WATCH_DIR/documents/report.txt"
echo "SELECT * FROM users;" > "$WATCH_DIR/documents/query.sql"
echo '{"name":"config"}' > "$WATCH_DIR/documents/config.json"
echo -e "${GRN}✓ Normal files — entropy ~3-5 bits${NC}"
sleep $DELAY

# Фаза 2: шифрование
echo ""
echo -e "${YEL}[PHASE 2] Ransomware encrypting files...${NC}"
echo -e "${YEL}⚠ Watch dashboard: http://localhost:3000${NC}"
echo ""

for i in {1..8}; do
    SIZE=$((64 + RANDOM % 128))
    dd if=/dev/urandom of="$WATCH_DIR/documents/encrypted_${i}.locked" \
       bs=1024 count=$SIZE 2>/dev/null
    echo -e "${RED}[$(date +%T)] encrypted_${i}.locked (${SIZE}KB) entropy≈8.0${NC}"
    sleep $DELAY
done

# Фаза 3: массовое шифрование
echo ""
echo -e "${RED}[PHASE 3] Mass encryption...${NC}"
for i in {1..5}; do
    dd if=/dev/urandom of="$WATCH_DIR/documents/LOCKED_${i}.enc" \
       bs=1024 count=64 2>/dev/null
    echo -e "${RED}[$(date +%T)] LOCKED_${i}.enc${NC}"
    sleep 1
done

echo ""
echo -e "${CYN}══════════════════════════════════════════════════${NC}"
echo -e "${CYN}  Dashboard:  http://localhost:3000${NC}"
echo -e "${CYN}  Incidents:  curl http://localhost:8000/incidents/list${NC}"
echo -e "${CYN}══════════════════════════════════════════════════${NC}"
echo ""

echo -e "${GRN}[RESULT] Waiting for detection (10s)...${NC}"
sleep 10

BEFORE=99
TOTAL=$(curl -s "http://localhost:8000/incidents/list?limit=200" | \
    python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
NEW=$((TOTAL - BEFORE))

LATEST=$(curl -s "http://localhost:8000/incidents/list?limit=1" | \
    python3 -c "
import sys,json
d=json.load(sys.stdin)
if d:
    r=d[0]
    print(f\"{r['action_taken'].upper()} | entropy={r['entropy']} | {r['time'][11:19]}\")
" 2>/dev/null)

echo -e "${RED}  Total incidents : $TOTAL${NC}"
echo -e "${RED}  New this run    : +$NEW${NC}"
echo -e "${RED}  Latest          : $LATEST${NC}"
echo ""
echo -e "${GRN}✓ Simulation complete. Check dashboard!${NC}"
