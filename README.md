# RansomGuard — Защищённая система резервного копирования

> Выпускная квалификационная работа бакалавра  
> НГАСУ (Сибстрин) · Кафедра информационных систем и технологий · 2026  
> Направление 09.03.02 «Информационные системы и технологии»

---

## О системе

**RansomGuard** — микросервисная система превентивной защиты от ransomware-атак с автоматическим резервным копированием. Система обнаруживает шифрование файлов в реальном времени на основе математического анализа энтропии Шеннона, автоматически изолирует угрозу и сохраняет резервные копии в защищённом WORM-репозитории.

### Ключевые возможности

- **Детекция в реальном времени** — агент вычисляет энтропию Шеннона H = −Σ p·log₂(p) для каждого изменённого файла. Нормальные файлы: H = 3–5 бит. Зашифрованные: H > 7.9 бит
- **Автоматическая реакция** — при обнаружении атаки система переводит директорию в режим read-only (lockdown) и инициирует экстренное резервное копирование
- **WORM-хранилище** — BorgBackup в режиме append-only: архивы невозможно изменить или удалить даже при компрометации системы
- **Zero Trust VPN** — весь трафик между сервисами зашифрован через WireGuard (ChaCha20-Poly1305)
- **Аудит-лог** — каждый инцидент фиксируется в изолированной SQLite БД для криминалистического анализа
- **Дашборд реального времени** — мониторинг энтропии, RPO/RTO метрик, истории инцидентов и бэкапов

---

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Агент мониторинга | Python 3.11 + watchdog |
| API шлюз | FastAPI + Uvicorn |
| База метрик | PostgreSQL + TimescaleDB |
| Аудит | SQLite |
| Резервное копирование | BorgBackup (WORM/append-only) |
| VPN туннель | WireGuard |
| Дашборд | Nuxt 4 + Vue 3.5 + Chart.js |
| Оркестрация | Docker + Docker Compose |

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │  Agent   │    │   Borg   │    │      WireGuard        │  │
│  │ watchdog │    │  backup  │    │   Zero Trust VPN      │  │
│  │ entropy  │    │  WORM    │    │   ChaCha20-Poly1305   │  │
│  └────┬─────┘    └────┬─────┘    └──────────────────────┘  │
│       │               │                                      │
│       └───────┬────────┘                                     │
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
vpn_net      wg1           — зашифрованный туннель агента и борга
```

---

## Быстрый старт

### Требования

- Docker 24+
- Docker Compose v2
- `make`
- `wireguard-tools` (для генерации ключей)

### Установка

```bash
git clone <repo>
cd ransomware-backup-system

# Установка: генерация WireGuard ключей + подготовка директорий
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
make status      # статус контейнеров + WireGuard
make logs        # логи всех сервисов
make check       # полная проверка всех компонентов
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
│   │   │   └── audit.py    # SQLite аудит
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # Nuxt 4 дашборд
│   ├── pages/index.vue     # главная страница
│   ├── components/         # StatCard, EntropyChart, AlertTable...
│   └── composables/
├── borg/                   # BorgBackup WORM сервис
│   ├── backup.py
│   └── Dockerfile
├── wireguard/              # WireGuard Zero Trust VPN
│   ├── config/             # конфиги и ключи (не в git)
│   ├── scripts/gen_keys.sh # генерация ключей
│   └── Dockerfile
├── db/migrations/          # SQL схемы TimescaleDB
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

- **Real-time detection** — the agent computes Shannon entropy H = −Σ p·log₂(p) for every modified file. Normal files score H = 3–5 bits; encrypted files score H > 7.9 bits
- **Automatic response** — upon detecting an attack, the system sets the monitored directory to read-only (lockdown) and triggers an emergency backup
- **WORM storage** — BorgBackup in append-only mode: archives cannot be modified or deleted even if the system is compromised
- **Zero Trust VPN** — all inter-service traffic is encrypted via WireGuard (ChaCha20-Poly1305)
- **Audit log** — every incident is recorded in an isolated SQLite database for forensic analysis
- **Real-time dashboard** — monitoring of entropy, RPO/RTO metrics, incident history, and backup events

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Monitoring agent | Python 3.11 + watchdog |
| API gateway | FastAPI + Uvicorn |
| Metrics database | PostgreSQL + TimescaleDB |
| Audit database | SQLite |
| Backup | BorgBackup (WORM/append-only) |
| VPN tunnel | WireGuard |
| Dashboard | Nuxt 4 + Vue 3.5 + Chart.js |
| Orchestration | Docker + Docker Compose |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │  Agent   │    │   Borg   │    │      WireGuard        │  │
│  │ watchdog │    │  backup  │    │   Zero Trust VPN      │  │
│  │ entropy  │    │  WORM    │    │   ChaCha20-Poly1305   │  │
│  └────┬─────┘    └────┬─────┘    └──────────────────────┘  │
│       │               │                                      │
│       └───────┬────────┘                                     │
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
- `wireguard-tools`

### Installation

```bash
git clone <repo>
cd ransomware-backup-system

# Generate WireGuard keys and prepare directories
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
make status      # container status + WireGuard
make logs        # logs from all services
make check       # full system health check
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

---

## License

MIT License — see [LICENSE](LICENSE)
