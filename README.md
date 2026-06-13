# RansomGuard — Защищённая система резервного копирования

> Выпускная квалификационная работа бакалавра  
> НГАСУ (Сибстрин) · Кафедра информационных систем и технологий · 2026  
> Направление 09.03.02 «Информационные системы и технологии»

---

## О системе

**RansomGuard** — микросервисная система превентивной защиты от ransomware-атак с автоматическим резервным копированием. Система обнаруживает шифрование файлов в реальном времени на основе математического анализа энтропии Шеннона, автоматически изолирует угрозу и сохраняет резервные копии в защищённом WORM-репозитории.

### Ключевые возможности

- **Двухуровневая детекция с корреляцией** — eBPF kprobe на `vfs_write` перехватывает запись на уровне ядра и **атрибутирует процесс-источник** (поведенческий сигнал), а энтропия Шеннона H = −Σ p·log₂(p) по содержимому файла даёт контентную детекцию. Авторитетный детектор — энтропийный слой (нормальные файлы 3–5 бит, зашифрованные > 7.9), который через атрибуцию eBPF связывает инцидент с конкретным PID
- **Точечная реакция** — при подтверждённом шифровании система **завершает процесс-источник** по PID (агент в `pid: host`), переводит директорию в read-only (lockdown) и инициирует внеплановый бэкап. Завершение инфраструктуры исключено whitelist'ом по реальному пути `/proc/pid/exe`
- **Защита от ложных срабатываний** — инцидент квалифицируется только комбинацией сигналов (контент + атрибуция); реальный системный шум (браузеры, БД) не эскалируется
- **Настоящий серверный WORM** — репозиторий на отдельном узле `borg-server`, доступном только по SSH через WireGuard; `borg serve --append-only` навязывает неизменяемость на стороне сервера, у клиента нет файлового доступа к репозиторию и он может выполнить лишь `borg serve`
- **Сетевая изоляция (Zero Trust)** — две изолированные Docker-сети + **реальный WireGuard-туннель** (10.8.0.0/24), по которому идёт весь трафик резервного копирования; репозиторий недостижим вне VPN
- **Аутентификация** — обмен метриками и управляющие действия защищены bearer-токеном (machine-to-machine)
- **Аудит-лог** — каждый инцидент фиксируется в изолированной SQLite БД для криминалистического анализа
- **Дашборд реального времени** — мониторинг энтропии, RPO/RTO метрик, истории инцидентов и бэкапов

---

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Перехват на уровне ядра | eBPF (BCC) — kprobe `vfs_write`, атрибуция процессов |
| Агент мониторинга | Python 3.11 + watchdog (inotify) + энтропия Шеннона |
| API шлюз | FastAPI + Uvicorn + slowapi (rate limiting) + bearer-auth |
| База метрик | PostgreSQL + TimescaleDB (hypertables) |
| Аудит | SQLite (append-only) |
| Резервное копирование | BorgBackup, серверный `borg serve --append-only` (WORM) |
| Узел хранения | отдельный `borg-server` по SSH через WireGuard |
| Сетевая изоляция | Docker bridge-сети + WireGuard-туннель (реальный транспорт бэкапов) |
| Дашборд | Nuxt 4 + Vue 3.5 + Chart.js |
| Тесты | pytest (87 тестов) |
| Оркестрация | Docker + Docker Compose (6 сервисов) |

---

## Архитектура

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Docker Compose (6 сервисов)                  │
│                                                                        │
│  ┌──────────┐  HTTP /backup  ┌──────────┐   ssh:// через WireGuard    │
│  │  Agent   │───────────────▶│   Borg   │═══════════════════╗         │
│  │ eBPF     │  (control)      │ (клиент) │   wg0 10.8.0.0/24 ║         │
│  │ watchdog │  атрибуция+kill └────┬─────┘                   ▼         │
│  │ entropy  │                      │              ┌────────────────┐  │
│  └────┬─────┘                      │              │   borg-server  │  │
│       │ HTTP+token                 │ HTTP+token   │ serve          │  │
│       ▼                            ▼              │ --append-only  │  │
│  ┌───────────────────┐                           │ (серверный WORM)│  │
│  │   FastAPI Backend │◀─── reset → agent /release└────────────────┘  │
│  └───────┬───────────┘                                                 │
│          │                                                             │
│   ┌──────▼───────┐   ┌────────────┐    ┌──────────────────────┐       │
│   │ TimescaleDB  │   │   SQLite   │    │   Nuxt 4 Dashboard   │       │
│   │  (метрики)   │   │  (аудит)   │    │  ← localhost:3000     │       │
│   └──────────────┘   └────────────┘    └──────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

### Сетевая изоляция

```
backend_net  172.20.0.0/24  — внутренний трафик сервисов
frontend_net               — изолированная сеть UI
wg0          10.8.0.0/24    — WireGuard-туннель borg-клиент ↔ borg-server
```

Репозиторий BorgBackup вынесен на отдельный узел `borg-server`, sshd которого
слушает **только** на адресе WireGuard-туннеля — хранилище недостижимо иначе как
через VPN (Zero Trust). Весь трафик резервного копирования (`borg create`,
`extract`, `break-lock`) идёт по туннелю. Эта же схема разворачивается на
несколько хостов в production.

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
├── borg/                   # BorgBackup клиент: бэкапит /monitored по ssh:// через WG
│   ├── backup.py           # плановые + emergency бэкапы, измеряемый RPO/RTO
│   ├── entrypoint.sh       # поднятие WireGuard-туннеля + запуск backup.py
│   └── Dockerfile
├── borg-server/            # Узел хранения: borg serve --append-only по SSH (WORM)
│   ├── entrypoint.sh       # WireGuard + sshd на адресе туннеля + forced-command
│   └── Dockerfile
├── wireguard/              # Ключи/конфиги WireGuard (генерируются при установке)
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

При превышении порога 7.2 бит агент регистрирует алерт. Реакция эскалируется по числу алертов в окне 30 секунд: ≥3 алертов (или подозрительное расширение) — внеплановый бэкап; ≥10 алертов или энтропия ≥7.9 — lockdown.

Параллельно eBPF-зонд на `vfs_write` ведёт **атрибуцию**: запоминает, какой процесс (PID) писал каждый файл. Когда энтропийный слой подтверждает шифрование, агент через атрибуцию eBPF получает PID источника и **завершает процесс** (`SIGKILL`), а не только блокирует каталог. Так корреляция контента (энтропия) и поведения/идентичности (eBPF) даёт точечную реакцию вместо реакции по одному сигналу.

---

## Тестирование

```bash
make test        # или: python3 -m pytest tests/ -v
```

87 модульных тестов покрывают математическое ядро системы:

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

- **Two-layer correlated detection** — an eBPF kprobe on `vfs_write` intercepts writes at the kernel level and **attributes the source process**, while Shannon entropy H = −Σ p·log₂(p) over file content does the content detection. The entropy layer is authoritative (normal 3–5 bits, encrypted > 7.9) and links an incident to a concrete PID via eBPF attribution
- **Targeted response** — on confirmed encryption the system **kills the source process** by PID (agent runs in `pid: host`), sets the directory read-only (lockdown), and triggers a backup. Infrastructure is protected by a real `/proc/pid/exe` path whitelist
- **False-positive protection** — an incident requires a combination of signals (content + attribution); real system noise (browsers, databases) is not escalated
- **True server-side WORM** — the repository lives on a separate `borg-server` node reachable only via SSH over WireGuard; `borg serve --append-only` enforces immutability server-side. The client has no filesystem access to the repo and can only run `borg serve`
- **Network isolation (Zero Trust)** — two isolated Docker networks plus a **real WireGuard tunnel** (10.8.0.0/24) carrying all backup traffic; the repository is unreachable outside the VPN
- **Authentication** — metric ingestion and control actions are protected by a machine-to-machine bearer token
- **Audit log** — every incident is recorded in an isolated SQLite database for forensic analysis
- **Real-time dashboard** — monitoring of entropy, RPO/RTO metrics, incident history, and backup events

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Kernel-level interception | eBPF (BCC) — kprobe `vfs_write`, process attribution |
| Monitoring agent | Python 3.11 + watchdog (inotify) + Shannon entropy |
| API gateway | FastAPI + Uvicorn + slowapi (rate limiting) + bearer auth |
| Metrics database | PostgreSQL + TimescaleDB (hypertables) |
| Audit database | SQLite (append-only) |
| Backup | BorgBackup, server-side `borg serve --append-only` (WORM) |
| Storage node | separate `borg-server` over SSH through WireGuard |
| Network isolation | Docker bridge networks + WireGuard tunnel (real backup transport) |
| Dashboard | Nuxt 4 + Vue 3.5 + Chart.js |
| Tests | pytest (87 tests) |
| Orchestration | Docker + Docker Compose (6 services) |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Docker Compose (6 services)                   │
│                                                                        │
│  ┌──────────┐  HTTP /backup  ┌──────────┐   ssh:// over WireGuard      │
│  │  Agent   │───────────────▶│   Borg   │═══════════════════╗          │
│  │ eBPF     │  (control)      │ (client) │   wg0 10.8.0.0/24 ║          │
│  │ watchdog │  attribute+kill └────┬─────┘                   ▼          │
│  │ entropy  │                      │              ┌────────────────┐   │
│  └────┬─────┘                      │              │   borg-server  │   │
│       │ HTTP+token                 │ HTTP+token   │ serve          │   │
│       ▼                            ▼              │ --append-only  │   │
│  ┌───────────────────┐                           │ (server WORM)  │   │
│  │   FastAPI Backend │◀─── reset → agent /release└────────────────┘   │
│  └───────┬───────────┘                                                 │
│          │                                                             │
│   ┌──────▼───────┐   ┌────────────┐    ┌──────────────────────┐        │
│   │ TimescaleDB  │   │   SQLite   │    │   Nuxt 4 Dashboard   │        │
│   │  (metrics)   │   │  (audit)   │    │  ← localhost:3000     │        │
│   └──────────────┘   └────────────┘    └──────────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
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

When entropy exceeds the 7.2-bit threshold, the agent registers an alert. The response escalates by alert count within a 30-second window: ≥3 alerts (or a suspicious extension) trigger an emergency backup; ≥10 alerts or entropy ≥7.9 trigger a lockdown.

In parallel, the eBPF probe on `vfs_write` performs **attribution** — recording which process (PID) wrote each file. When the entropy layer confirms encryption, the agent resolves the source PID via eBPF attribution and **kills the process** (`SIGKILL`), not just locking the directory. Correlating content (entropy) with behaviour/identity (eBPF) yields a targeted response instead of acting on a single signal.

In parallel, the eBPF monitor tracks per-process write rates at the kernel level: ≥50 writes in 10 seconds or ≥5 MB/s from a non-whitelisted process is a behavioral signature of an encryptor, triggering an immediate response.

---

## Testing

```bash
make test        # or: python3 -m pytest tests/ -v
```

87 unit tests cover the mathematical core of the system: Shannon entropy (boundary cases, the 7.2-bit threshold), the eBPF process whitelist and ransomware-extension detection, RTO estimation, and incident escalation logic. Tests run without Docker or databases — external dependencies are mocked in `tests/conftest.py`.

---

## License

MIT License — see [LICENSE](LICENSE)
