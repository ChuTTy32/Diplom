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
LOCKDOWN_DURATION = 60  # секунд до автосброса

alert_timestamps: list = []
alert_lock = threading.Lock()
lockdown_active = False
lockdown_timer: threading.Timer | None = None


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


def report_incident(trigger_file: str, entropy: float, alert_count: int) -> str:
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
    global lockdown_active
    now = time.time()

    with alert_lock:
        alert_timestamps.append(now)
        cutoff = now - ATTACK_WINDOW_SEC
        while alert_timestamps and alert_timestamps[0] < cutoff:
            alert_timestamps.pop(0)
        count = len(alert_timestamps)

        # Флаг ставим под локом ДО старта потока — иначе два быстрых алерта
        # успевают пройти проверку и запустить два execute_response.
        if count < ATTACK_THRESHOLD or lockdown_active:
            return
        lockdown_active = True

    threading.Thread(
        target=execute_response,
        args=(file_path, entropy, count),
        daemon=True,
    ).start()


def execute_response(trigger_file: str, entropy: float, alert_count: int):
    global lockdown_timer

    action = report_incident(trigger_file, entropy, alert_count)

    if action == "lockdown":
        if _chmod_recursive(WATCH_PATH, "444"):
            log.critical(f"🔒 LOCKDOWN: {WATCH_PATH} → read-only (444)")

    if action in ("lockdown", "emergency_backup"):
        trigger_emergency_backup()

    # Автосброс через LOCKDOWN_DURATION секунд
    lockdown_timer = threading.Timer(LOCKDOWN_DURATION, release_lockdown)
    lockdown_timer.daemon = True
    lockdown_timer.start()
    log.info(f"⏱ Lockdown auto-release in {LOCKDOWN_DURATION}s")


# ─── Watchdog ─────────────────────────────────────────────────────────

SKIP_EXTENSIONS = {".tmp", ".swp", ".lock", ".part"}


class EntropyHandler(FileSystemEventHandler):
    def _process(self, path: str):
        if not os.path.isfile(path):
            return
        if os.path.splitext(path)[1].lower() in SKIP_EXTENSIONS:
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
    inotify-событий. Файл обрабатывается только если mtime изменился
    с прошлого прохода: иначе каждый старый .locked-файл генерировал бы
    повторный алерт каждые SCAN_INTERVAL секунд, заваливая БД.
    """
    seen_mtimes: dict[str, float] = {}
    while True:
        log.info(f"Full scan: {WATCH_PATH}")
        for root, _, files in os.walk(WATCH_PATH):
            for fname in files:
                path = os.path.join(root, fname)
                if os.path.splitext(fname)[1].lower() in SKIP_EXTENSIONS:
                    continue
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if seen_mtimes.get(path) == mtime:
                    continue
                seen_mtimes[path] = mtime
                entropy = file_entropy(path)
                if entropy == 0.0:
                    continue
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
                send_entropy(path, entropy, size, entropy >= ENTROPY_THRESHOLD)
        # Подчистка записей об удалённых файлах
        if len(seen_mtimes) > 10000:
            seen_mtimes = {p: m for p, m in seen_mtimes.items() if os.path.exists(p)}
        send_system_metrics()
        time.sleep(SCAN_INTERVAL)


def on_ebpf_suspect(pid: int, comm: str, writes: int,
                    bytes_per_sec: float, sample_file: str):
    """
    Callback от eBPF: процесс проявляет поведение ransomware
    (аномально высокая частота записи в файлы).

    eBPF уже агрегировал ≥50 записей в окне — это сформировавшаяся атака,
    порог ATTACK_THRESHOLD не нужен. Запускаем реакцию напрямую.
    entropy=0.0 — поведенческая детекция, содержимое не анализировалось;
    действие на бэкенде определяет alert_count (= количество записей).
    """
    global lockdown_active
    trigger = f"[eBPF] proc={comm} pid={pid} file={sample_file}"
    log.warning(
        f"[eBPF] SUSPECT proc={comm} pid={pid} "
        f"writes={writes} bps={bytes_per_sec/1024:.0f}KB/s"
    )

    with alert_lock:
        if lockdown_active:
            return
        lockdown_active = True

    threading.Thread(
        target=execute_response,
        args=(trigger, 0.0, writes),
        daemon=True,
    ).start()


def main():
    log.info(f"Agent starting. watch={WATCH_PATH} threshold={ENTROPY_THRESHOLD}")
    os.makedirs(WATCH_PATH, exist_ok=True)

    # ── Буфер метрик ────────────────────────────────────────────────
    threading.Thread(target=_flush_loop, daemon=True, name="buf-flush").start()

    # ── eBPF (уровень ядра) ──────────────────────────────────────────
    ebpf = EBPFMonitor(on_suspect=on_ebpf_suspect)
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
