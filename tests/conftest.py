"""
Конфигурация тестового окружения RansomGuard.

Подключает пути к исходникам и мокает библиотеки, недоступные
без привилегированного окружения (bcc/eBPF, psutil, watchdog, httpx).
Все тесты выполняются на хосте без Docker.
"""

import sys
import os
import types
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Исходники агента, borg и backend доступны напрямую
sys.path.insert(0, os.path.join(ROOT, "agent"))
sys.path.insert(0, os.path.join(ROOT, "borg"))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def _mock(name: str, **attrs) -> types.ModuleType:
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


# bcc — требует привилегированного ядра с eBPF
_mock("bcc", BPF=MagicMock())

# watchdog — inotify-наблюдатель (не нужен в unit-тестах)
_mock("watchdog")
_mock("watchdog.observers", Observer=MagicMock())
_mock("watchdog.events", FileSystemEventHandler=object)

# psutil — системные метрики (мок с разумными значениями)
_mock(
    "psutil",
    cpu_percent=MagicMock(return_value=5.0),
    virtual_memory=MagicMock(return_value=MagicMock(percent=30.0)),
    disk_usage=MagicMock(return_value=MagicMock(percent=20.0)),
    net_io_counters=MagicMock(
        return_value=MagicMock(bytes_recv=1024 * 100, bytes_sent=1024 * 50)
    ),
)

# httpx — HTTP-клиент (запросы к бэкенду не нужны в unit-тестах)
_mock("httpx", post=MagicMock())

# dotenv — загрузка .env (не нужна в тестах)
_mock("dotenv", load_dotenv=MagicMock())
