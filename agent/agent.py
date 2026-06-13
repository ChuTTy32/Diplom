"""
Агент мониторинга файловой системы.
- eBPF kprobe/vfs_write — перехват на уровне ядра (поведенческий анализ)
- watchdog (inotify) — real-time события файловой системы
- Энтропия Шеннона — детекция ransomware по содержимому файлов
- Автоматическая реакция: lockdown + экстренный бэкап

eBPF активен при privileged-контейнере. При недоступности — watchdog-fallback.
"""

import os
import math
import time
import signal
import logging
import socket
import subprocess
import collections
import threading
import httpx
import psutil

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ebpf_monitor import EBPFMonitor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
# httpx логирует каждый запрос на INFO — оставляем только предупреждения
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("agent")

BACKEND_URL       = os.getenv("BACKEND_URL", "http://backend:8000")
WATCH_PATH        = os.getenv("WATCH_PATH", "/monitored")
ENTROPY_THRESHOLD = float(os.getenv("ENTROPY_THRESHOLD", "7.2"))
SCAN_INTERVAL     = int(os.getenv("SCAN_INTERVAL", "5"))
SIGNAL_DIR        = os.getenv("SIGNAL_DIR", "/signals")
HOSTNAME          = socket.gethostname()

ATTACK_WINDOW_SEC = 30
ATTACK_THRESHOLD  = 3
# Автосброс lockdown через N секунд. 0 — отключить автосброс (production:
# снятие только вручную оператором после проверки). По умолчанию 60 — для демо,
# чтобы ложный инцидент не блокировал каталог навсегда.
LOCKDOWN_DURATION = int(os.getenv("LOCKDOWN_DURATION", "60"))
RESPONSE_COOLDOWN = 10  # минимум секунд между реакциями (эскалация разрешена)

# Зеркала порогов lockdown из backend-policy (app/core/policy.py) —
# фоновый эскалатор должен знать, когда burst дорос до блокировки
ESCALATION_ALERT_COUNT = 10
ESCALATION_ENTROPY     = 7.9

alert_timestamps: list = []
alert_lock = threading.Lock()
lockdown_active = False                          # реальный lockdown (chmod 444)
lockdown_timer: threading.Timer | None = None
_last_response_ts = 0.0                          # время последней реакции
_last_alert_file    = ""                         # последний алерт — для эскалатора
_last_alert_entropy = 0.0
_ebpf = None                                     # ссылка на EBPFMonitor для атрибуции


# ─── Энтропия Шеннона ────────────────────────────────────────────────

def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counter = collections.Counter(data)
    total = len(data)
    entropy = 0.0
    for count in counter.values():
        p = count / total
        entropy -= p * math.log2(p)
    return round(entropy, 6)


def file_entropy(path: str, max_bytes: int = 65536) -> float:
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        return shannon_entropy(data)
    except (OSError, PermissionError):
        return 0.0


# ─── HTTP ─────────────────────────────────────────────────────────────

BUFFER_MAX   = 500          # не накапливать больше N метрик в памяти
_buf: list   = []           # буфер entropy-метрик при недоступности бэкенда
_buf_lock    = threading.Lock()


def _flush_buffer() -> bool:
    """
    Отправляет накопленные метрики. Возвращает True если бэкенд доступен.
    Вызывается и из send_entropy, и из фонового flush-потока.
    """
    with _buf_lock:
        if not _buf:
            return True
        batch = list(_buf)

    sent = 0
    for item in batch:
        try:
            httpx.post(f"{BACKEND_URL}/metrics/entropy", json=item, timeout=5.0)
            sent += 1
        except Exception:
            break  # бэкенд всё ещё недоступен — прекращаем, не трогаем буфер

    if sent:
        with _buf_lock:
            del _buf[:sent]
        log.info(f"Buffer flushed {sent}/{len(batch)} metrics")

    return sent == len(batch)


def _flush_loop():
    """Фоновый поток: каждые 30 сек пробует опустошить буфер."""
    while True:
        time.sleep(30)
        if _buf:
            _flush_buffer()


def send_entropy(file_path: str, entropy: float, file_size: int, alert: bool):
    payload = {
        "file_path": file_path, "entropy": entropy,
        "file_size": file_size, "alert": alert, "host": HOSTNAME,
    }
    # Сначала пробуем сбросить накопленное, потом отправить текущее
    backend_ok = _flush_buffer()
    if backend_ok:
        try:
            httpx.post(f"{BACKEND_URL}/metrics/entropy", json=payload, timeout=5.0)
            if alert:
                log.warning(f"⚠ ALERT entropy={entropy:.4f} file={file_path}")
                register_alert(file_path, entropy)
            return
        except Exception as e:
            log.error(f"send_entropy failed: {e}")

    # Бэкенд недоступен — буферизуем
    with _buf_lock:
        if len(_buf) < BUFFER_MAX:
            _buf.append(payload)
        else:
            log.warning(f"Buffer full ({BUFFER_MAX}), dropping metric for {file_path}")

    # Алерты регистрируем локально в любом случае
    if alert:
        log.warning(f"⚠ ALERT (buffered) entropy={entropy:.4f} file={file_path}")
        register_alert(file_path, entropy)


def send_system_metrics():
    try:
        disk = psutil.disk_usage(WATCH_PATH)
        net  = psutil.net_io_counters()
        httpx.post(
            f"{BACKEND_URL}/metrics/system",
            json={
                "cpu_pct":    psutil.cpu_percent(interval=1),
                "mem_pct":    psutil.virtual_memory().percent,
                "disk_pct":   disk.percent,
                "net_in_kb":  net.bytes_recv / 1024,
                "net_out_kb": net.bytes_sent / 1024,
            },
            timeout=5.0,
        )
    except Exception as e:
        log.error(f"send_system_metrics failed: {e}")


def report_incident(trigger_file: str, entropy: float, alert_count: int,
                    suspicious_ext: bool = False) -> str:
    try:
        severity = "critical" if alert_count >= 10 or entropy >= 7.9 else "warning"
        resp = httpx.post(
            f"{BACKEND_URL}/incidents/report",
            json={
                "severity": severity,
                "trigger_file": trigger_file,
                "entropy": entropy,
                "alert_count": alert_count,
                "host": HOSTNAME,
                "suspicious_ext": suspicious_ext,
            },
            timeout=5.0,
        )
        data = resp.json()
        action = data.get("action", "logged")
        log.warning(f"🚨 INCIDENT → action={action} | {data.get('message')}")
        return action
    except Exception as e:
        log.error(f"report_incident failed: {e}")
        return "logged"


# ─── Lockdown ─────────────────────────────────────────────────────────

def _chmod_recursive(path: str, mode: str) -> bool:
    """chmod без shell — аргументы передаются списком, инъекция невозможна."""
    try:
        subprocess.run(["chmod", "-R", mode, path], check=False, capture_output=True)
        return True
    except OSError as e:
        log.error(f"chmod {mode} {path} failed: {e}")
        return False


def release_lockdown():
    """Снимаем lockdown — восстанавливаем права директории."""
    global lockdown_active, lockdown_timer
    lockdown_active = False
    lockdown_timer = None
    with alert_lock:
        alert_timestamps.clear()

    if _chmod_recursive(WATCH_PATH, "755"):
        log.info(f"🔓 Lockdown released — {WATCH_PATH} restored to 755")


# Критическая инфраструктура — НИКОГДА не завершаем. Whitelist по РЕАЛЬНОМУ
# пути исполняемого файла (/proc/pid/exe), а не по comm: comm обрезается до
# 15 символов и легко подделывается, путь бинаря — нет.
_PROTECTED_EXE = frozenset({
    "borg", "postgres", "postmaster", "systemd", "init",
    "dockerd", "containerd", "sshd",
})


def _proc_exe(pid: int) -> str:
    """Путь исполняемого файла процесса (агент в pid: host видит хостовые PID)."""
    try:
        return os.path.realpath(f"/proc/{pid}/exe")
    except OSError:
        return ""


def _kill_process(pid: int | None, reason: str = "") -> bool:
    """
    Принудительно завершает процесс-источник шифрования. PID приходит из
    атрибуции eBPF (пространство хоста), поэтому агент запускается с pid: host.
    Защита: не трогаем init (PID 1), собственный процесс и критическую
    инфраструктуру (по пути бинаря), чтобы не повредить саму систему.
    """
    if pid is None or pid <= 1 or pid == os.getpid():
        return False
    exe = _proc_exe(pid)
    if os.path.basename(exe) in _PROTECTED_EXE:
        log.info(f"kill pid={pid} skipped — protected ({exe})")
        return False
    try:
        os.kill(pid, signal.SIGKILL)
        log.critical(f"🔪 KILLED process pid={pid} exe={exe} {reason}")
        return True
    except ProcessLookupError:
        return False  # процесс уже завершился
    except (PermissionError, OSError) as e:
        log.error(f"kill pid={pid} failed: {e}")
        return False


def _attribute_pid(file_path: str) -> int | None:
    """
    Кто писал этот файл? Спрашиваем атрибуцию eBPF по basename.
    Связывает контентную детекцию (энтропия в /monitored) с процессом-источником.
    """
    if _ebpf is None:
        return None
    attr = _ebpf.attribute(os.path.basename(file_path))
    return attr[0] if attr else None


def trigger_emergency_backup():
    """
    Сигнал borg-сервису через разделяемый volume (/signals).
    Borg опрашивает сигнальный файл и запускает внеплановый бэкап.
    """
    try:
        os.makedirs(SIGNAL_DIR, exist_ok=True)
        with open(os.path.join(SIGNAL_DIR, "emergency_backup"), "w") as f:
            f.write(str(time.time()))
        log.warning("🆘 Emergency backup signal sent to borg")
    except OSError as e:
        log.error(f"emergency signal failed: {e}")


def register_alert(file_path: str, entropy: float):
    global _last_response_ts, _last_alert_file, _last_alert_entropy
    now = time.time()

    with alert_lock:
        alert_timestamps.append(now)
        _last_alert_file = file_path
        _last_alert_entropy = entropy
        cutoff = now - ATTACK_WINDOW_SEC
        while alert_timestamps and alert_timestamps[0] < cutoff:
            alert_timestamps.pop(0)
        count = len(alert_timestamps)

        if lockdown_active or count < ATTACK_THRESHOLD:
            return
        # Кулдаун вместо полного запрета: если атака продолжается после
        # emergency_backup, через RESPONSE_COOLDOWN секунд count вырастет
        # и реакция эскалирует до lockdown. Метку времени ставим под локом
        # ДО старта потока — иначе два быстрых алерта запускают две реакции.
        if now - _last_response_ts < RESPONSE_COOLDOWN:
            return
        _last_response_ts = now

    # Атрибуция вне лока: связываем файл (контентная детекция) с процессом
    pid = _attribute_pid(file_path)
    threading.Thread(
        target=execute_response,
        args=(file_path, entropy, count),
        kwargs={"pid": pid},
        daemon=True,
    ).start()


def _escalation_loop():
    """
    Фоновая эскалация. Событийный путь (register_alert) срабатывает только
    при ПОСТУПЛЕНИИ алерта: если burst целиком попал в кулдаун-окно после
    первой реакции, а новых событий нет, окно с count >= порога lockdown
    осталось бы без ответа. Раз в 2с перепроверяем и доводим до lockdown.
    """
    global _last_response_ts
    while True:
        time.sleep(2)
        now = time.time()
        with alert_lock:
            cutoff = now - ATTACK_WINDOW_SEC
            while alert_timestamps and alert_timestamps[0] < cutoff:
                alert_timestamps.pop(0)
            count = len(alert_timestamps)

            if lockdown_active or count < ATTACK_THRESHOLD:
                continue
            if now - _last_response_ts < RESPONSE_COOLDOWN:
                continue
            # Эскалируем только если burst дорос до уровня lockdown —
            # иначе плодили бы дубликаты emergency_backup каждый кулдаун
            if count < ESCALATION_ALERT_COUNT and _last_alert_entropy < ESCALATION_ENTROPY:
                continue
            _last_response_ts = now
            trigger, entropy = _last_alert_file, _last_alert_entropy

        log.warning(f"⏫ Escalation: sustained burst count={count} → responding")
        execute_response(trigger, entropy, count, pid=_attribute_pid(trigger))


def execute_response(trigger_file: str, entropy: float, alert_count: int,
                     suspicious_ext: bool = False, pid: int | None = None):
    global lockdown_active, lockdown_timer

    action = report_incident(trigger_file, entropy, alert_count, suspicious_ext)

    # Точечная реакция: завершаем процесс-источник ТОЛЬКО при подтверждённом
    # шифровании (lockdown — энтропия ≥7.9 или устойчивый burst), не на
    # одиночный подозрительный файл (emergency_backup). PID даёт атрибуция eBPF;
    # это снижает риск ложного убийства легитимного процесса.
    if pid is not None and action == "lockdown":
        _kill_process(pid, reason=f"file={trigger_file}")

    if action == "lockdown":
        lockdown_active = True
        if _chmod_recursive(WATCH_PATH, "444"):
            log.critical(f"🔒 LOCKDOWN: {WATCH_PATH} → read-only (444)")
        # Автосброс только при LOCKDOWN_DURATION > 0 (демо-режим). В production
        # (LOCKDOWN_DURATION=0) снятие lockdown — вручную оператором через API
        # после верификации, чтобы не переоткрыть данные во время атаки.
        if LOCKDOWN_DURATION > 0:
            lockdown_timer = threading.Timer(LOCKDOWN_DURATION, release_lockdown)
            lockdown_timer.daemon = True
            lockdown_timer.start()
            log.info(f"⏱ Lockdown auto-release in {LOCKDOWN_DURATION}s")
        else:
            log.info("⏱ Lockdown auto-release отключён (только ручной сброс)")

    if action in ("lockdown", "emergency_backup"):
        trigger_emergency_backup()


# ─── Watchdog ─────────────────────────────────────────────────────────

SKIP_EXTENSIONS = {".tmp", ".swp", ".lock", ".part"}

# Дедупликация по mtime, общая для watchdog и full_scan. Двойная задача:
#  1) full_scan не пересылает неизменённые файлы каждые SCAN_INTERVAL сек;
#  2) гасит события IN_ATTRIB от СОБСТВЕННЫХ chmod при lockdown/release —
#     иначе автоколебание: release → chmod 755 → inotify → повторные алерты
#     по старым зашифрованным файлам → новый lockdown → release → ...
#     (chmod меняет ctime, но не mtime — дедупликация это использует)
_mtime_seen: dict = {}
_mtime_lock = threading.Lock()


def _changed_since_last_scan(path: str) -> bool:
    """True если файл новый или его mtime изменился с прошлой обработки."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return False
    with _mtime_lock:
        if _mtime_seen.get(path) == mtime:
            return False
        if len(_mtime_seen) > 10000:
            for stale in [p for p in _mtime_seen if not os.path.exists(p)]:
                del _mtime_seen[stale]
        _mtime_seen[path] = mtime
    return True


class EntropyHandler(FileSystemEventHandler):
    def _process(self, path: str):
        if not os.path.isfile(path):
            return
        if os.path.splitext(path)[1].lower() in SKIP_EXTENSIONS:
            return
        if not _changed_since_last_scan(path):
            return
        entropy = file_entropy(path)
        if entropy == 0.0:
            return
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        send_entropy(path, entropy, size, entropy >= ENTROPY_THRESHOLD)

    def on_modified(self, event):
        if not event.is_directory:
            self._process(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._process(event.src_path)


def full_scan():
    """
    Периодический обход WATCH_PATH — страховка на случай пропуска
    inotify-событий. Использует общую mtime-дедупликацию: неизменённые
    файлы (включая старые .locked из прошлых атак) не пересылаются.
    """
    while True:
        log.info(f"Full scan: {WATCH_PATH}")
        for root, _, files in os.walk(WATCH_PATH):
            for fname in files:
                path = os.path.join(root, fname)
                if os.path.splitext(fname)[1].lower() in SKIP_EXTENSIONS:
                    continue
                if not _changed_since_last_scan(path):
                    continue
                entropy = file_entropy(path)
                if entropy == 0.0:
                    continue
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
                send_entropy(path, entropy, size, entropy >= ENTROPY_THRESHOLD)
        send_system_metrics()
        time.sleep(SCAN_INTERVAL)


def on_ebpf_suspect(pid: int, comm: str, writes: int,
                    bytes_per_sec: float, sample_file: str,
                    suspicious_ext: bool = False):
    """
    Сигнал eBPF: процесс проявляет признаки ransomware (аномальный burst записи
    либо запись файла с расширением шифровальщика).

    eBPF — слой АТРИБУЦИИ и поведенческой корреляции, а НЕ самостоятельный
    триггер инцидента: kprobe видит записи всей системы и не знает полный путь
    файла, поэтому реакция по расширению вне /monitored давала бы ложные
    срабатывания (например, borg при восстановлении архива). Авторитетное
    решение принимает энтропийный слой (скоуплен на /monitored, анализирует
    контент), используя атрибуцию eBPF (`attribute()`) для точечного завершения
    процесса-источника. Здесь сигнал только фиксируется в журнал.
    """
    kind = "ransomware-ext" if suspicious_ext else f"burst writes={writes}"
    log.info(
        f"[eBPF] kernel signal: proc={comm} pid={pid} ({kind}) "
        f"bps={bytes_per_sec/1024:.0f}KB/s file={sample_file}"
    )


def main():
    log.info(f"Agent starting. watch={WATCH_PATH} threshold={ENTROPY_THRESHOLD}")
    os.makedirs(WATCH_PATH, exist_ok=True)

    # ── Буфер метрик ────────────────────────────────────────────────
    threading.Thread(target=_flush_loop, daemon=True, name="buf-flush").start()

    # ── Фоновая эскалация (burst в кулдаун-окне → lockdown) ─────────
    threading.Thread(target=_escalation_loop, daemon=True, name="escalation").start()

    # ── eBPF (уровень ядра) ──────────────────────────────────────────
    global _ebpf
    ebpf = EBPFMonitor(on_suspect=on_ebpf_suspect)
    _ebpf = ebpf                      # для атрибуции из энтропийного слоя
    ebpf_active = ebpf.start()
    if not ebpf_active:
        log.warning("Running in watchdog-only mode (no eBPF)")

    # ── watchdog (уровень inotify) ───────────────────────────────────
    observer = Observer()
    observer.schedule(EntropyHandler(), WATCH_PATH, recursive=True)
    observer.start()

    scanner = threading.Thread(target=full_scan, daemon=True)
    scanner.start()

    log.info(
        f"Agent ready. eBPF={'ON' if ebpf_active else 'OFF'} "
        f"watchdog=ON watch={WATCH_PATH}"
    )

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        ebpf.stop()
    observer.join()


if __name__ == "__main__":
    main()
