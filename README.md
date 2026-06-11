# RansomGuard — Защищённая система резервного копирования

> Выпускная квалификационная работа бакалавра  
> НГАСУ (Сибстрин) · Кафедра информационных систем и технологий · 2026  
> Направление 09.03.02 «Информационные системы и технологии»

---

## О системе

**RansomGuard** — микросервисная система превентивной защиты от ransomware-атак с автоматическим резервным копированием. Система обнаруживает шифрование файлов в реальном времени на основе математического анализа энтропии Шеннона, автоматически изолирует угрозу и сохраняет резервные копии в защищённом WORM-репозитории.

### Ключевые возможности

- **Двухуровневая детекция** — eBPF kprobe на `vfs_write` перехватывает запись в файлы на уровне ядра (поведенческий анализ частоты записи), агент вычисляет энтропию Шеннона H = −Σ p·log₂(p) для каждого изменённого файла. Нормальные файлы: H = 3–5 бит. Зашифрованные: H > 7.9 бит
- **Защита от ложных срабатываний** — whitelist легитимных процессов (компиляторы, git, borg) + детекция ransomware-расширений (.locked, .enc, .wncry), пробивающая whitelist
- **Автоматическая реакция** — при обнаружении атаки система переводит директорию в режим read-only (lockdown) и сигнализирует borg-сервису о внеплановом бэкапе через разделяемый volume
- **WORM-хранилище** — BorgBackup в режиме append-only: архивы невозможно изменить или удалить даже при компрометации системы
- **Сетевая изоляция** — сервисы разнесены по изолированным Docker-сетям (Zero Trust); для multi-host развёртывания подготовлены конфигурации WireGuard VPN
- **Аудит-лог** — каждый инцидент фиксируется в изолированной SQLite БД для криминалистического анализа
- **Дашборд реального времени** — мониторинг энтропии, RPO/RTO метрик, истории инцидентов и бэкапов

---

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Перехват на уровне ядра | eBPF (BCC) — kprobe `vfs_write` |
| Агент мониторинга | Python 3.11 + watchdog (inotify fallback) |
| API шлюз | FastAPI + Uvicorn + slowapi (rate limiting) |
| База метрик | PostgreSQL + TimescaleDB (hypertables) |
| Аудит | SQLite (append-only) |
| Резервное копирование | BorgBackup (WORM/append-only) |
| Сетевая изоляция | Docker bridge-сети; WireGuard для multi-host (production) |
| Дашборд | Nuxt 4 + Vue 3.5 + Chart.js |
| Тесты | pytest (84 теста) |
| Оркестрация | Docker + Docker Compose |

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
│                                                             │
│  ┌──────────┐  signal   ┌──────────┐                        │
│  │  Agent   │──────────▶│   Borg   │                        │
│  │ eBPF     │ /signals  │  backup  │                        │
│  │ watchdog │           │  WORM    │                        │
│  │ entropy  │           │append-only│                       │
│  └────┬─────┘           └────┬─────┘                        │
│       │                      │                               │
│       └──────────┬───────────┘                               │
│               │ HTTP/REST                                    │
│       ┌───────▼──────────┐                                  │
│       │    FastAPI        │                                  │
│       │    Backend        │                                  │
│       └───────┬──────────┘                                  │
│               │                                             │
│       ┌───────▼──────────┐    ┌────────────┐               │
│       │  TimescaleDB     │    │   SQLite   │               │
│       │  (метрики)       │    │  (аудит)   │               │
│       └──────────────────┘    └────────────┘               │
│                                                             │
│  ┌──────────────────────┐                                   │
│  │   Nuxt 4 Dashboard   │ ← http://localhost:3000           │
│  │   real-time polling  │                                   │
│  └──────────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
```

### Сетевая изоляция

```
backend_net  172.20.0.0/24  — внутренний трафик сервисов
frontend_net               — изолированная сеть UI
```

Для multi-host развёртывания (агенты на отдельных машинах) подготовлены
конфигурации WireGuard VPN — см. `wireguard/`. В однохостовой демонстрации
VPN не используется: трафик не покидает изолированные Docker-сети.

---

## Быстрый старт

### Требования

- Docker 24+
- Docker Compose v2
- `make`

### Установка

```bash
git clone <repo>
cd ransomware-backup-system

# Установка: создание .env с секретами + подготовка директорий
make install

# Запуск всех сервисов
make start
```

После запуска:
- Дашборд: **http://localhost:3000**
- API (Swagger): **http://localhost:8000/docs**

---

## Команды управления

```bash
make help        # список всех команд
make install     # первоначальная установка
make start       # запустить систему
make stop        # остановить систему
make restart     # перезапустить
make status      # статус контейнеров и API
make logs        # логи всех сервисов
make check       # полная проверка всех компонентов
make test        # модульные тесты (pytest)
make demo        # симуляция ransomware-атаки (для демо)
make demo-fast   # ускоренная симуляция
make reset       # сбросить lockdown после атаки
make clean       # удалить все данные и контейнеры
```

---

## Демонстрация

Для показа работы системы на защите:

```bash
# 1. Запустить систему
make start

# 2. Открыть дашборд в браузере
# http://localhost:3000

# 3. Запустить симуляцию атаки
make demo-fast

# 4. Наблюдать на дашборде:
#    - рост счётчика алертов
#    - скачок энтропии на графике
#    - появление инцидентов в таблице
#    - автоматический lockdown

# 5. Проверить аудит-лог
curl http://localhost:8000/incidents/audit
```

---

## API эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/metrics/entropy` | Приём метрик энтропии от агента |
| `GET`  | `/metrics/entropy` | История метрик энтропии |
| `POST` | `/metrics/backup` | Регистрация события бэкапа |
| `GET`  | `/metrics/backup` | История бэкапов |
| `POST` | `/metrics/system` | Системные метрики (CPU/RAM/Disk) |
| `GET`  | `/metrics/system` | История системных метрик |
| `GET`  | `/metrics/summary` | Сводка для дашборда |
| `POST` | `/incidents/report` | Регистрация инцидента |
| `GET`  | `/incidents/list` | Список инцидентов |
| `GET`  | `/incidents/audit` | Полный аудит-лог |
| `POST` | `/incidents/reset-lockdown` | Сброс lockdown |
| `GET`  | `/health` | Health check |

Полная документация: `http://localhost:8000/docs`

---

## Конфигурация

Все параметры в файле `.env`:

```env
# База данных
POSTGRES_USER=admin
POSTGRES_PASSWORD=secret
POSTGRES_DB=metrics

# Агент
WATCH_PATH=/tmp/monitored      # директория мониторинга
ENTROPY_THRESHOLD=7.2          # порог энтропии для алерта
SCAN_INTERVAL=5                # интервал сканирования (секунды)

# BorgBackup
BORG_PASSPHRASE=changeme       # пароль шифрования репозитория
```

---

## Структура проекта

```
ransomware-backup-system/
├── agent/                  # Python агент мониторинга
│   ├── agent.py            # watchdog + энтропия Шеннона + реакция
│   ├── ebpf_monitor.py     # eBPF kprobe/vfs_write + whitelist
│   ├── Dockerfile
│   └── requirements.txt
├── backend/                # FastAPI API шлюз
│   ├── app/
│   │   ├── api/
│   │   │   ├── metrics.py  # эндпоинты метрик
│   │   │   └── incidents.py # управление инцидентами
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py # TimescaleDB
│   │   │   ├── policy.py   # доменная логика реагирования
│   │   │   ├── limiter.py  # rate limiting
│   │   │   └── audit.py    # SQLite аудит
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # Nuxt 4 дашборд
│   └── app/
│       ├── pages/index.vue # главная страница
│       ├── components/     # StatCard, EntropyChart, IncidentTable...
│       └── composables/
├── borg/                   # BorgBackup WORM сервис
│   ├── backup.py           # плановые + emergency бэкапы, RPO/RTO
│   └── Dockerfile
├── wireguard/              # WireGuard VPN (production multi-host, в демо не используется)
├── db/migrations/          # SQL схемы TimescaleDB (hypertables)
├── tests/                  # pytest: энтропия, whitelist, RTO, инциденты
├── docker-compose.yml
├── Makefile
├── simulate_attack.sh      # симуляция ransomware для демо
└── .env
```

---

## Принцип работы детекции

Ransomware шифрует файлы — после шифрования распределение байт становится равномерным (каждый байт встречается с вероятностью 1/256). Энтропия Шеннона измеряет эту равномерность:

```
H(X) = -Σ p(x) · log₂(p(x))
```

| Тип файла | Энтропия |
|-----------|----------|
| Текст (.txt, .py) | 3.5 – 5.0 бит |
| Исполняемый (.exe) | 5.5 – 6.5 бит |
| Сжатый (.zip, .gz) | 7.0 – 7.5 бит |
| **Зашифрованный** | **7.8 – 8.0 бит** |

При превышении порога 7.2 бит агент регистрирует алерт. При трёх алертах за 30 секунд — инцидент и lockdown.

Параллельно eBPF-монитор отслеживает частоту записи каждого процесса на уровне ядра: ≥50 записей за 10 секунд или ≥5 МБ/с от процесса вне whitelist — поведенческий признак шифровальщика, реакция запускается немедленно.

---

## Тестирование

```bash
make test        # или: python3 -m pytest tests/ -v
```

84 модульных теста покрывают математическое ядро системы:

| Файл | Что проверяется |
|------|-----------------|
| `tests/test_entropy.py` | Формула Шеннона: граничные случаи, порог 7.2, файловое сканирование |
| `tests/test_whitelist.py` | Whitelist процессов и детекция ransomware-расширений |
| `tests/test_rto.py` | Расчёт RTO: формула, fallback, монотонность |
| `tests/test_incident.py` | Логика эскалации (lockdown/emergency_backup/logged), SQLite аудит |

Тесты выполняются без Docker и БД — внешние зависимости замоканы в `tests/conftest.py`.

---

---

# RansomGuard — Ransomware-Resistant Backup System

> Bachelor's Thesis  
> NSUACE (Sibstrin) · Department of Information Systems and Technologies · 2026  
> Program 09.03.02 «Information Systems and Technologies»

---

## Overview

**RansomGuard** is a microservice-based system for proactive ransomware protection with automated backup. The system detects file encryption in real time using Shannon entropy analysis, automatically isolates the threat, and stores backups in a protected WORM repository.

### Key Features

- **Two-layer detection** — an eBPF kprobe on `vfs_write` intercepts file writes at the kernel level (behavioral write-rate analysis), while the agent computes Shannon entropy H = −Σ p·log₂(p) for every modified file. Normal files score H = 3–5 bits; encrypted files score H > 7.9 bits
- **False-positive protection** — a whitelist of legitimate processes (compilers, git, borg) combined with ransomware-extension detection (.locked, .enc, .wncry) that overrides the whitelist
- **Automatic response** — upon detecting an attack, the system sets the monitored directory to read-only (lockdown) and signals the borg service for an immediate emergency backup via a shared volume
- **WORM storage** — BorgBackup in append-only mode: archives cannot be modified or deleted even if the system is compromised
- **Network isolation** — services are separated into isolated Docker networks (Zero Trust); WireGuard VPN configurations are provided for multi-host deployments
- **Audit log** — every incident is recorded in an isolated SQLite database for forensic analysis
- **Real-time dashboard** — monitoring of entropy, RPO/RTO metrics, incident history, and backup events

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Kernel-level interception | eBPF (BCC) — kprobe `vfs_write` |
| Monitoring agent | Python 3.11 + watchdog (inotify fallback) |
| API gateway | FastAPI + Uvicorn + slowapi (rate limiting) |
| Metrics database | PostgreSQL + TimescaleDB (hypertables) |
| Audit database | SQLite (append-only) |
| Backup | BorgBackup (WORM/append-only) |
| Network isolation | Docker bridge networks; WireGuard for multi-host (production) |
| Dashboard | Nuxt 4 + Vue 3.5 + Chart.js |
| Tests | pytest (84 tests) |
| Orchestration | Docker + Docker Compose |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
│                                                             │
│  ┌──────────┐  signal   ┌──────────┐                        │
│  │  Agent   │──────────▶│   Borg   │                        │
│  │ eBPF     │ /signals  │  backup  │                        │
│  │ watchdog │           │  WORM    │                        │
│  │ entropy  │           │append-only│                       │
│  └────┬─────┘           └────┬─────┘                        │
│       │                      │                               │
│       └──────────┬───────────┘                               │
│               │ HTTP/REST                                    │
│       ┌───────▼──────────┐                                  │
│       │    FastAPI        │                                  │
│       │    Backend        │                                  │
│       └───────┬──────────┘                                  │
│               │                                             │
│       ┌───────▼──────────┐    ┌────────────┐               │
│       │  TimescaleDB     │    │   SQLite   │               │
│       │  (metrics)       │    │  (audit)   │               │
│       └──────────────────┘    └────────────┘               │
│                                                             │
│  ┌──────────────────────┐                                   │
│  │   Nuxt 4 Dashboard   │ ← http://localhost:3000           │
│  │   real-time polling  │                                   │
│  └──────────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Requirements

- Docker 24+
- Docker Compose v2
- `make`

### Installation

```bash
git clone <repo>
cd ransomware-backup-system

# Create .env with generated secrets and prepare directories
make install

# Start all services
make start
```

After startup:
- Dashboard: **http://localhost:3000**
- API (Swagger): **http://localhost:8000/docs**

---

## Management Commands

```bash
make help        # list all commands
make install     # first-time setup
make start       # start all services
make stop        # stop all services
make restart     # restart all services
make status      # container and API status
make logs        # logs from all services
make check       # full system health check
make test        # unit tests (pytest)
make demo        # simulate a ransomware attack
make demo-fast   # fast simulation
make reset       # release lockdown after an attack
make clean       # remove all containers and volumes
```

---

## Demo

To demonstrate the system during a presentation:

```bash
# 1. Start the system
make start

# 2. Open dashboard in browser
# http://localhost:3000

# 3. Run attack simulation
make demo-fast

# 4. Watch on dashboard:
#    - alert counter increasing
#    - entropy spike on the chart
#    - new incidents appearing in the table
#    - automatic lockdown triggered

# 5. Check audit log
curl http://localhost:8000/incidents/audit
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/metrics/entropy` | Receive entropy metrics from agent |
| `GET`  | `/metrics/entropy` | Entropy metrics history |
| `POST` | `/metrics/backup` | Register backup event |
| `GET`  | `/metrics/backup` | Backup history |
| `POST` | `/metrics/system` | System metrics (CPU/RAM/Disk) |
| `GET`  | `/metrics/system` | System metrics history |
| `GET`  | `/metrics/summary` | Dashboard summary |
| `POST` | `/incidents/report` | Report an incident |
| `GET`  | `/incidents/list` | List incidents |
| `GET`  | `/incidents/audit` | Full audit log |
| `POST` | `/incidents/reset-lockdown` | Release lockdown |
| `GET`  | `/health` | Health check |

Full docs: `http://localhost:8000/docs`

---

## Configuration

All parameters in `.env`:

```env
# Database
POSTGRES_USER=admin
POSTGRES_PASSWORD=secret
POSTGRES_DB=metrics

# Agent
WATCH_PATH=/tmp/monitored      # monitored directory
ENTROPY_THRESHOLD=7.2          # entropy alert threshold
SCAN_INTERVAL=5                # scan interval (seconds)

# BorgBackup
BORG_PASSPHRASE=changeme       # repository encryption passphrase
```

---

## How Detection Works

Ransomware encrypts files — after encryption, byte distribution becomes uniform (each byte occurs with probability 1/256). Shannon entropy measures this uniformity:

```
H(X) = -Σ p(x) · log₂(p(x))
```

| File type | Entropy |
|-----------|---------|
| Text (.txt, .py) | 3.5 – 5.0 bits |
| Executable (.exe) | 5.5 – 6.5 bits |
| Compressed (.zip, .gz) | 7.0 – 7.5 bits |
| **Encrypted** | **7.8 – 8.0 bits** |

When entropy exceeds the 7.2-bit threshold, the agent registers an alert. Three alerts within 30 seconds trigger an incident and lockdown.

In parallel, the eBPF monitor tracks per-process write rates at the kernel level: ≥50 writes in 10 seconds or ≥5 MB/s from a non-whitelisted process is a behavioral signature of an encryptor, triggering an immediate response.

---

## Testing

```bash
make test        # or: python3 -m pytest tests/ -v
```

84 unit tests cover the mathematical core of the system: Shannon entropy (boundary cases, the 7.2-bit threshold), the eBPF process whitelist and ransomware-extension detection, RTO estimation, and incident escalation logic. Tests run without Docker or databases — external dependencies are mocked in `tests/conftest.py`.

---

## License

MIT License — see [LICENSE](LICENSE)
