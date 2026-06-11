"""
Тесты бизнес-логики реагирования на инциденты.

Тестируется реальная доменная функция backend/app/core/policy.py
(не копия — Clean Architecture позволяет импортировать ядро без FastAPI):

  alert_count ≥ 10 или entropy ≥ 7.9  →  lockdown
  alert_count ≥ 3                      →  emergency_backup
  иначе                                →  logged
"""

import sys
import os
import pytest

from app.core.policy import (
    determine_action,
    LOCKDOWN_ALERT_COUNT,
    LOCKDOWN_ENTROPY,
    BACKUP_ALERT_COUNT,
)


def _action(alert_count: int, entropy: float) -> str:
    return determine_action(alert_count, entropy)[0]


class TestIncidentActionLogic:
    def test_high_alert_count_triggers_lockdown(self):
        assert _action(10, 5.0) == "lockdown"

    def test_alert_count_above_ten_is_lockdown(self):
        assert _action(99, 3.0) == "lockdown"

    def test_high_entropy_alone_triggers_lockdown(self):
        # Энтропия 7.9 — порог WannaCry-уровня шифрования
        assert _action(1, 7.9) == "lockdown"

    def test_entropy_above_threshold_is_lockdown(self):
        assert _action(0, 8.0) == "lockdown"
        assert _action(2, 7.95) == "lockdown"

    def test_moderate_alerts_trigger_emergency_backup(self):
        assert _action(3, 6.5) == "emergency_backup"
        assert _action(5, 7.0) == "emergency_backup"

    def test_low_count_low_entropy_just_logged(self):
        assert _action(1, 4.0) == "logged"
        assert _action(2, 7.89) == "logged"

    def test_boundary_alert_count_nine_not_lockdown(self):
        # 9 < 10 и entropy < 7.9 → emergency_backup, не lockdown
        assert _action(9, 7.0) == "emergency_backup"

    def test_boundary_entropy_just_below_lockdown(self):
        # 7.89 < 7.9 → не lockdown
        assert _action(2, 7.89) != "lockdown"

    def test_thresholds_are_consistent(self):
        # Константы политики: lockdown строже emergency_backup
        assert LOCKDOWN_ALERT_COUNT > BACKUP_ALERT_COUNT
        assert LOCKDOWN_ENTROPY == pytest.approx(7.9)

    def test_message_matches_action(self):
        action, message = determine_action(50, 0.0)
        assert action == "lockdown"
        assert "CRITICAL" in message

        action, message = determine_action(3, 5.0)
        assert action == "emergency_backup"
        assert "WARNING" in message

        action, message = determine_action(1, 3.0)
        assert action == "logged"
        assert "INFO" in message

    # ─── eBPF-специфичные сценарии ──────────────────────────────────────
    # Агент при eBPF-детекции отправляет entropy=0.0 (поведенческий анализ,
    # содержимое не читалось) и alert_count = числу записей в окне (≥50).

    def test_ebpf_burst_writes_trigger_lockdown(self):
        assert _action(50, 0.0) == "lockdown"

    def test_ebpf_zero_entropy_does_not_block_action(self):
        # entropy=0.0 не должна мешать эскалации по количеству записей
        assert _action(100, 0.0) == "lockdown"

    def test_single_alert_is_not_lockdown(self):
        # Одиночный алерт не должен блокировать систему
        assert _action(1, 7.0) == "logged"


class TestAuditLog:
    """Тесты изолированного SQLite аудит-лога."""

    def test_log_incident_and_retrieve(self, tmp_path):
        # Переопределяем путь к SQLite для теста
        os.environ["SQLITE_PATH"] = str(tmp_path / "test_audit.db")
        # Перезагружаем модуль чтобы подхватил новый путь
        if "app.core.audit" in sys.modules:
            del sys.modules["app.core.audit"]

        from app.core.audit import init_db, log_incident, get_incidents

        init_db()
        inc_id = log_incident(
            severity="critical",
            trigger_file="/monitored/secret.locked",
            entropy=7.95,
            alert_count=15,
            action_taken="lockdown",
            host="test-host",
        )

        assert inc_id is not None
        incidents = get_incidents(limit=10)
        assert len(incidents) == 1
        assert incidents[0]["severity"] == "critical"
        assert incidents[0]["action_taken"] == "lockdown"
        assert incidents[0]["entropy"] == pytest.approx(7.95)

    def test_audit_log_append_only(self, tmp_path):
        os.environ["SQLITE_PATH"] = str(tmp_path / "audit2.db")
        if "app.core.audit" in sys.modules:
            del sys.modules["app.core.audit"]

        from app.core.audit import init_db, log_audit, get_audit_log

        init_db()
        log_audit(event="INCIDENT_LOCKDOWN", detail="file=test.locked", host="host1")
        log_audit(event="LOCKDOWN_RESET",   detail="manual reset",      host="host1")

        entries = get_audit_log(limit=10)
        assert len(entries) == 2
        # Порядок: последний сверху
        assert entries[0]["event"] == "LOCKDOWN_RESET"
        assert entries[1]["event"] == "INCIDENT_LOCKDOWN"
