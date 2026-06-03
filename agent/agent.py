"""
Агент мониторинга файловой системы.
- watchdog для real-time событий
- Энтропия Шеннона для детекции ransomware
- Автоматическая реакция: lockdown + экстренный бэкап
- Поддержка сброса lockdown через API
"""

import os
import math
import time
import logging
import socket
import collections
import threading
import httpx
import psutil

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("agent")

BACKEND_URL       = os.getenv("BACKEND_URL", "http://backend:8000")
WATCH_PATH        = os.getenv("WATCH_PATH", "/monitored")
ENTROPY_THRESHOLD = float(os.getenv("ENTROPY_THRESHOLD", "7.2"))
SCAN_INTERVAL     = int(os.getenv("SCAN_INTERVAL", "5"))
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

def send_entropy(file_path: str, entropy: float, file_size: int, alert: bool):
    try:
        httpx.post(
            f"{BACKEND_URL}/metrics/entropy",
            json={"file_path": file_path, "entropy": entropy,
                  "file_size": file_size, "alert": alert, "host": HOSTNAME},
            timeout=5.0,
        )
        if alert:
            log.warning(f"⚠ ALERT entropy={entropy:.4f} file={file_path}")
            register_alert(file_path, entropy)
    except Exception as e:
        log.error(f"send_entropy failed: {e}")


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

def release_lockdown():
    """Снимаем lockdown — восстанавливаем права директории."""
    global lockdown_active, lockdown_timer
    lockdown_active = False
    lockdown_timer = None
    with alert_lock:
        alert_timestamps.clear()

    try:
        os.system(f"chmod -R 755 {WATCH_PATH}")
        log.info(f"🔓 Lockdown released — {WATCH_PATH} restored to 755")
    except Exception as e:
        log.error(f"release_lockdown failed: {e}")


def register_alert(file_path: str, entropy: float):
    global lockdown_active
    now = time.time()

    with alert_lock:
        alert_timestamps.append(now)
        cutoff = now - ATTACK_WINDOW_SEC
        while alert_timestamps and alert_timestamps[0] < cutoff:
            alert_timestamps.pop(0)
        count = len(alert_timestamps)

    if count >= ATTACK_THRESHOLD and not lockdown_active:
        threading.Thread(
            target=execute_response,
            args=(file_path, entropy, count),
            daemon=True,
        ).start()


def execute_response(trigger_file: str, entropy: float, alert_count: int):
    global lockdown_active, lockdown_timer
    lockdown_active = True

    action = report_incident(trigger_file, entropy, alert_count)

    if action == "lockdown":
        try:
            os.system(f"chmod -R 444 {WATCH_PATH}")
            log.critical(f"🔒 LOCKDOWN: {WATCH_PATH} → read-only (444)")
        except Exception as e:
            log.error(f"lockdown chmod failed: {e}")

    if action in ("lockdown", "emergency_backup"):
        try:
            with open("/tmp/emergency_backup", "w") as f:
                f.write(f"{time.time()}")
            log.warning("🆘 Emergency backup triggered")
        except Exception as e:
            log.error(f"emergency trigger failed: {e}")

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
    while True:
        log.info(f"Full scan: {WATCH_PATH}")
        for root, _, files in os.walk(WATCH_PATH):
            for fname in files:
                path = os.path.join(root, fname)
                if os.path.splitext(fname)[1].lower() in SKIP_EXTENSIONS:
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


def main():
    log.info(f"Agent starting. watch={WATCH_PATH} threshold={ENTROPY_THRESHOLD}")
    os.makedirs(WATCH_PATH, exist_ok=True)

    observer = Observer()
    observer.schedule(EntropyHandler(), WATCH_PATH, recursive=True)
    observer.start()

    scanner = threading.Thread(target=full_scan, daemon=True)
    scanner.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
