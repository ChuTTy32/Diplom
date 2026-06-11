# =============================================================================
# RansomGuard — Makefile
# Использование: make <команда>
# =============================================================================

.PHONY: help install start stop restart status logs logs-agent logs-backend \
        demo demo-fast check reset clean open test

# ─── Переменные ──────────────────────────────────────────────────────
# Читаем WATCH_PATH из .env, fallback /tmp/monitored
WATCH_PATH := $(shell grep '^WATCH_PATH=' .env 2>/dev/null | cut -d= -f2 | tr -d '"')
WATCH_PATH := $(or $(WATCH_PATH),/tmp/monitored)

# Docker: без sudo если пользователь в группе docker
DOCKER := $(shell docker info >/dev/null 2>&1 && echo "docker" || echo "sudo docker")
DC     := $(DOCKER) compose

# Цвета
RED := \033[0;31m
GRN := \033[0;32m
YEL := \033[1;33m
CYN := \033[0;36m
DIM := \033[2m
NC  := \033[0m

# ─── Справка ─────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "$(CYN)╔══════════════════════════════════════════════╗$(NC)"
	@echo "$(CYN)║         RansomGuard — Backup Monitor         ║$(NC)"
	@echo "$(CYN)╚══════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "  $(GRN)make install$(NC)      — первоначальная установка"
	@echo "  $(GRN)make start$(NC)        — запустить все сервисы"
	@echo "  $(GRN)make stop$(NC)         — остановить все сервисы"
	@echo "  $(GRN)make restart$(NC)      — перезапустить все сервисы"
	@echo "  $(GRN)make status$(NC)       — статус контейнеров и API"
	@echo "  $(GRN)make logs$(NC)         — логи всех сервисов"
	@echo "  $(GRN)make logs-agent$(NC)   — следить за логами агента"
	@echo "  $(GRN)make logs-backend$(NC) — следить за логами backend"
	@echo "  $(GRN)make demo$(NC)         — симуляция ransomware-атаки"
	@echo "  $(GRN)make demo-fast$(NC)    — быстрая симуляция (--fast)"
	@echo "  $(GRN)make check$(NC)        — полная проверка системы"
	@echo "  $(GRN)make test$(NC)         — запустить модульные тесты (pytest)"
	@echo "  $(GRN)make reset$(NC)        — сбросить lockdown"
	@echo "  $(GRN)make clean$(NC)        — удалить контейнеры и volumes"
	@echo "  $(GRN)make open$(NC)         — открыть дашборд в браузере"
	@echo ""
	@echo "  $(DIM)WATCH_PATH = $(WATCH_PATH)$(NC)"
	@echo ""

# ─── Установка ───────────────────────────────────────────────────────
install:
	@bash setup.sh

# ─── Запуск ──────────────────────────────────────────────────────────
start:
	@echo "$(CYN)[START] Запуск всех сервисов...$(NC)"
	@mkdir -p $(WATCH_PATH)
	@$(DC) up -d --build
	@echo ""
	@echo "$(DIM)Ожидание backend (до 60 сек)...$(NC)"
	@timeout 60 bash -c 'until curl -sf http://localhost:8000/health >/dev/null 2>&1; do sleep 2; printf "."; done; echo ""' || \
		echo "$(YEL)⚠ Backend не ответил за 60s — проверьте: make logs-backend$(NC)"
	@echo ""
	@$(MAKE) --no-print-directory status

# ─── Остановка ───────────────────────────────────────────────────────
stop:
	@echo "$(YEL)[STOP] Остановка сервисов...$(NC)"
	@$(DC) down
	@echo "$(GRN)✓ Сервисы остановлены$(NC)"

# ─── Перезапуск ──────────────────────────────────────────────────────
restart:
	@$(MAKE) --no-print-directory stop
	@$(MAKE) --no-print-directory start

# ─── Статус ──────────────────────────────────────────────────────────
status:
	@echo "$(CYN)[STATUS] Контейнеры:$(NC)"
	@$(DC) ps
	@echo ""
	@echo "$(CYN)[STATUS] API Health:$(NC)"
	@curl -s http://localhost:8000/health 2>/dev/null && echo "" || echo "  $(RED)Backend недоступен$(NC)"
	@echo ""

# ─── Логи ────────────────────────────────────────────────────────────
logs:
	@echo "--- AGENT (last 15) ---"
	@$(DOCKER) logs agent --tail 15 2>/dev/null || true
	@echo ""
	@echo "--- BACKEND (last 10) ---"
	@$(DOCKER) logs backend --tail 10 2>/dev/null || true
	@echo ""
	@echo "--- BORG (last 5) ---"
	@$(DOCKER) logs borg --tail 5 2>/dev/null || true

logs-agent:
	@$(DOCKER) logs agent --follow

logs-backend:
	@$(DOCKER) logs backend --follow

# ─── Демо атаки ──────────────────────────────────────────────────────
demo:
	@bash simulate_attack.sh

demo-fast:
	@bash simulate_attack.sh --fast

# ─── Полная проверка ─────────────────────────────────────────────────
check:
	@echo "$(CYN)╔══════════════════════════════════════════════╗$(NC)"
	@echo "$(CYN)║         ПОЛНАЯ ПРОВЕРКА СИСТЕМЫ              ║$(NC)"
	@echo "$(CYN)╚══════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(CYN)[1/7] Контейнеры:$(NC)"
	@$(DC) ps
	@echo ""
	@echo "$(CYN)[2/7] API Health:$(NC)"
	@curl -s http://localhost:8000/health && echo "" || echo "  $(RED)FAIL$(NC)"
	@echo ""
	@echo "$(CYN)[3/7] Метрики (summary):$(NC)"
	@curl -s http://localhost:8000/metrics/summary | \
		python3 -c "import sys,json; d=json.load(sys.stdin); \
		print(f'  alerts={d[\"total_alerts\"]} | avg_entropy={d[\"avg_entropy_1h\"]} | RPO={d[\"rpo_minutes\"]}m | last_backup={str(d[\"last_backup\"])[:19]}')" \
		2>/dev/null || echo "  Нет данных"
	@echo ""
	@echo "$(CYN)[4/7] Инциденты:$(NC)"
	@curl -s "http://localhost:8000/incidents/list?limit=200" | \
		python3 -c "import sys,json; d=json.load(sys.stdin); \
		[print(f'  [{r[\"severity\"]:8s}] {r[\"action_taken\"]:20s} entropy={r[\"entropy\"]:.4f}  {str(r[\"time\"])[11:19]}') for r in d[:5]] \
		if d else print('  No incidents')" 2>/dev/null || echo "  Нет данных"
	@echo ""
	@echo "$(CYN)[5/7] BorgBackup архивы:$(NC)"
	@$(DOCKER) exec borg borg list /repo 2>/dev/null | tail -5 | \
		awk '{print "  " $$0}' || echo "  Borg недоступен"
	@echo ""
	@echo "$(CYN)[6/7] Модульные тесты:$(NC)"
	@python3 -m pytest tests/ -q 2>/dev/null | tail -1 | awk '{print "  " $$0}' || echo "  pytest не установлен"
	@echo ""
	@echo "$(CYN)[7/7] Frontend:$(NC)"
	@curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://localhost:3000 || echo "  $(RED)FAIL$(NC)"
	@echo ""
	@echo "$(GRN)✓ Проверка завершена$(NC)"

# ─── Сброс lockdown ──────────────────────────────────────────────────
reset:
	@echo "$(YEL)[RESET] Сброс lockdown...$(NC)"
	@curl -s -X POST http://localhost:8000/incidents/reset-lockdown > /dev/null
	@chmod -R 755 $(WATCH_PATH) 2>/dev/null || true
	@echo "$(GRN)✓ Lockdown снят. WATCH_PATH=$(WATCH_PATH) → 755$(NC)"

# ─── Очистка ─────────────────────────────────────────────────────────
clean:
	@echo "$(RED)[CLEAN] Удаление контейнеров и volumes...$(NC)"
	@$(DC) down -v
	@rm -rf $(WATCH_PATH)
	@echo "$(GRN)✓ Очищено$(NC)"

# ─── Тесты ───────────────────────────────────────────────────────────
test:
	@echo "$(CYN)[TEST] Модульные тесты (pytest)...$(NC)"
	@python3 -m pytest tests/ -v

# ─── Открыть дашборд ─────────────────────────────────────────────────
open:
	@xdg-open http://localhost:3000 2>/dev/null || \
	 open http://localhost:3000 2>/dev/null || \
	 echo "Открой браузер: http://localhost:3000"
