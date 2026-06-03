# =============================================================================
# RansomGuard — Makefile
# Использование: make <команда>
# =============================================================================

.PHONY: help install start stop restart status logs demo clean reset check

# Цвета
RED    := \033[0;31m
GRN    := \033[0;32m
YEL    := \033[1;33m
CYN    := \033[0;36m
NC     := \033[0m

help:
	@echo ""
	@echo "$(CYN)╔══════════════════════════════════════════════╗$(NC)"
	@echo "$(CYN)║         RansomGuard — Backup Monitor         ║$(NC)"
	@echo "$(CYN)╚══════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "  $(GRN)make install$(NC)   — первоначальная установка (ключи WireGuard + папки)"
	@echo "  $(GRN)make start$(NC)     — запустить все сервисы"
	@echo "  $(GRN)make stop$(NC)      — остановить все сервисы"
	@echo "  $(GRN)make restart$(NC)   — перезапустить все сервисы"
	@echo "  $(GRN)make status$(NC)    — статус всех контейнеров"
	@echo "  $(GRN)make logs$(NC)      — логи всех сервисов (последние 20 строк)"
	@echo "  $(GRN)make demo$(NC)      — запустить симуляцию ransomware-атаки"
	@echo "  $(GRN)make check$(NC)     — полная проверка системы"
	@echo "  $(GRN)make reset$(NC)     — сбросить lockdown и права директории"
	@echo "  $(GRN)make clean$(NC)     — удалить все контейнеры и volumes"
	@echo ""

# ─── Установка ───────────────────────────────────────────────────────
install:
	@echo "$(CYN)[INSTALL] Подготовка системы...$(NC)"
	@sudo apt-get install -y wireguard-tools 2>/dev/null || true
	@mkdir -p /tmp/monitored
	@sudo chown -R $$USER:$$USER /tmp/monitored
	@mkdir -p wireguard/config backend/app/data
	@if [ ! -f wireguard/config/wg1.conf ]; then \
		echo "$(YEL)[INSTALL] Генерация WireGuard ключей...$(NC)"; \
		sudo bash wireguard/scripts/gen_keys.sh; \
	else \
		echo "$(GRN)[INSTALL] WireGuard ключи уже существуют$(NC)"; \
	fi
	@echo "$(GRN)[INSTALL] Готово! Запустите: make start$(NC)"

# ─── Запуск ──────────────────────────────────────────────────────────
start:
	@echo "$(CYN)[START] Запуск всех сервисов...$(NC)"
	@mkdir -p /tmp/monitored
	@sudo chown -R $$USER:$$USER /tmp/monitored
	@sudo docker compose up -d --build
	@echo ""
	@echo "$(GRN)✓ Сервисы запущены:$(NC)"
	@echo "  Dashboard : http://localhost:3000"
	@echo "  API       : http://localhost:8000"
	@echo "  Swagger   : http://localhost:8000/docs"
	@echo ""
	@$(MAKE) status

# ─── Остановка ───────────────────────────────────────────────────────
stop:
	@echo "$(YEL)[STOP] Остановка сервисов...$(NC)"
	@sudo docker compose down
	@sudo ip link delete wg1 2>/dev/null || true
	@echo "$(GRN)✓ Сервисы остановлены$(NC)"

# ─── Перезапуск ──────────────────────────────────────────────────────
restart:
	@$(MAKE) stop
	@sleep 2
	@$(MAKE) start

# ─── Статус ──────────────────────────────────────────────────────────
status:
	@echo "$(CYN)[STATUS] Контейнеры:$(NC)"
	@sudo docker compose ps
	@echo ""
	@echo "$(CYN)[STATUS] WireGuard:$(NC)"
	@sudo docker exec wireguard wg show wg1 2>/dev/null || echo "  WireGuard не запущен"
	@echo ""
	@echo "$(CYN)[STATUS] API Health:$(NC)"
	@curl -s http://localhost:8000/health 2>/dev/null || echo "  Backend недоступен"
	@echo ""

# ─── Логи ────────────────────────────────────────────────────────────
logs:
	@echo "$(CYN)[LOGS] Последние события:$(NC)"
	@echo ""
	@echo "--- AGENT ---"
	@sudo docker logs agent --tail 10 2>/dev/null
	@echo ""
	@echo "--- BACKEND ---"
	@sudo docker logs backend --tail 5 2>/dev/null
	@echo ""
	@echo "--- BORG ---"
	@sudo docker logs borg --tail 5 2>/dev/null

logs-agent:
	@sudo docker logs agent --follow

logs-backend:
	@sudo docker logs backend --follow

# ─── Демо атаки ──────────────────────────────────────────────────────
demo:
	@echo "$(RED)[DEMO] Запуск симуляции ransomware-атаки...$(NC)"
	@bash simulate_attack.sh

demo-fast:
	@echo "$(RED)[DEMO] Быстрая симуляция...$(NC)"
	@bash simulate_attack.sh --fast

# ─── Полная проверка ─────────────────────────────────────────────────
check:
	@echo "$(CYN)╔══════════════════════════════════════════════╗$(NC)"
	@echo "$(CYN)║         ПОЛНАЯ ПРОВЕРКА СИСТЕМЫ              ║$(NC)"
	@echo "$(CYN)╚══════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(CYN)[1/6] Контейнеры:$(NC)"
	@sudo docker compose ps
	@echo ""
	@echo "$(CYN)[2/6] API Health:$(NC)"
	@curl -s http://localhost:8000/health && echo ""
	@echo ""
	@echo "$(CYN)[3/6] Метрики (summary):$(NC)"
	@curl -s http://localhost:8000/metrics/summary | \
		python3 -c "import sys,json; d=json.load(sys.stdin); \
		print(f'  Alerts: {d[\"total_alerts\"]} | Entropy: {d[\"avg_entropy_1h\"]} | RPO: {d[\"rpo_minutes\"]}m | Last backup: {str(d[\"last_backup\"])[:19]}')"
	@echo ""
	@echo "$(CYN)[4/6] Инциденты:$(NC)"
	@curl -s "http://localhost:8000/incidents/list?limit=200" | \
		python3 -c "import sys,json; d=json.load(sys.stdin); \
		print(f'  Total: {len(d)} | Latest: {d[0][\"action_taken\"]} at {str(d[0][\"time\"])[11:19]}') if d else print('  No incidents')"
	@echo ""
	@echo "$(CYN)[5/6] BorgBackup архивы:$(NC)"
	@sudo docker exec borg borg list /repo 2>/dev/null | tail -3 | \
		awk '{print "  " $$0}' || echo "  Borg недоступен"
	@echo ""
	@echo "$(CYN)[6/6] WireGuard:$(NC)"
	@sudo docker exec wireguard wg show wg1 2>/dev/null | \
		grep -E "interface|public key|peer|allowed" | \
		awk '{print "  " $$0}' || echo "  WireGuard недоступен"
	@echo ""
	@echo "$(CYN)[7/6] Frontend:$(NC)"
	@curl -s -o /dev/null -w "  HTTP Status: %{http_code}\n" http://localhost:3000
	@echo ""
	@echo "$(GRN)✓ Проверка завершена$(NC)"

# ─── Сброс lockdown ──────────────────────────────────────────────────
reset:
	@echo "$(YEL)[RESET] Сброс lockdown...$(NC)"
	@curl -s -X POST http://localhost:8000/incidents/reset-lockdown > /dev/null
	@sudo chown -R $$USER:$$USER /tmp/monitored 2>/dev/null || true
	@sudo find /tmp/monitored -type d -exec chmod 755 {} \; 2>/dev/null || true
	@sudo find /tmp/monitored -type f -exec chmod 644 {} \; 2>/dev/null || true
	@echo "$(GRN)✓ Lockdown снят, права восстановлены$(NC)"

# ─── Очистка ─────────────────────────────────────────────────────────
clean:
	@echo "$(RED)[CLEAN] Удаление всех данных...$(NC)"
	@sudo docker compose down -v
	@sudo ip link delete wg1 2>/dev/null || true
	@sudo rm -rf /tmp/monitored
	@echo "$(GRN)✓ Очищено$(NC)"

# ─── Открыть дашборд ─────────────────────────────────────────────────
open:
	@xdg-open http://localhost:3000 2>/dev/null || \
	 open http://localhost:3000 2>/dev/null || \
	 echo "Открой браузер: http://localhost:3000"
