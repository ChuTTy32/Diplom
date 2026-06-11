import json
import os
import time
import subprocess
import logging
import httpx
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("borg")

BORG_REPO       = os.getenv("BORG_REPO", "/repo")
BORG_PASSPHRASE = os.getenv("BORG_PASSPHRASE", "changeme")
BACKUP_SOURCE   = os.getenv("BACKUP_SOURCE", "/monitored")
BACKEND_URL     = os.getenv("BACKEND_URL", "http://backend:8000")
INTERVAL_SEC    = int(os.getenv("BACKUP_INTERVAL_SEC", "300"))

# Скорость чтения с диска при восстановлении (MB/s).
# 100 MB/s — консервативная оценка для SATA SSD.
# Переопределяется через env RESTORE_SPEED_MB_PER_SEC.
RESTORE_SPEED_MB_PER_SEC = float(os.getenv("RESTORE_SPEED_MB_PER_SEC", "100.0"))
BORG_OVERHEAD_SEC        = 30  # фиксированные накладные расходы: init + mount

env = {**os.environ, "BORG_PASSPHRASE": BORG_PASSPHRASE}
last_backup_time = None


def report(event_type: str, **kwargs):
    try:
        httpx.post(f"{BACKEND_URL}/metrics/backup",
                   json={"event_type": event_type, **kwargs}, timeout=5.0)
    except Exception as e:
        log.error(f"report failed: {e}")


def init_repo():
    result = subprocess.run(
        ["borg", "init", "--encryption=repokey", "--append-only", BORG_REPO],
        env=env, capture_output=True, text=True,
    )
    if result.returncode not in (0, 2):
        log.error(f"borg init failed: {result.stderr}")
    else:
        log.info("Borg repo ready (append-only, repokey encryption)")


def get_compressed_size(archive: str) -> int:
    """
    Возвращает сжатый размер архива в байтах.
    Использует `borg info --json`, который даёт структурированный вывод.
    При ошибке возвращает 0 — вызывающий код переключится на fallback.
    """
    try:
        r = subprocess.run(
            ["borg", "info", "--json", archive],
            env=env, capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return 0
        data = json.loads(r.stdout)
        return int(data["archives"][0]["stats"]["compressed_size"])
    except Exception as exc:
        log.warning(f"get_compressed_size failed: {exc}")
        return 0


def estimate_rto(compressed_bytes: int, backup_duration_sec: int) -> int:
    """
    RTO (Recovery Time Objective) — оценка времени восстановления в минутах.

    Если сжатый размер архива известен:
        RTO = compressed_size / restore_speed + overhead
    Иначе (fallback):
        RTO ≈ backup_duration (создание и восстановление симметричны по I/O)

    Нижняя граница: 1 минута.
    """
    if compressed_bytes > 0:
        restore_bytes_per_sec = RESTORE_SPEED_MB_PER_SEC * 1024 * 1024
        rto_sec = (compressed_bytes / restore_bytes_per_sec) + BORG_OVERHEAD_SEC
        return max(1, int(rto_sec / 60))
    # Fallback: время создания ≈ время восстановления (симметричный I/O)
    return max(1, int(backup_duration_sec / 60) + 1)


def do_backup():
    global last_backup_time
    archive = f"{BORG_REPO}::backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    report("start", archive_name=archive)

    t0 = time.time()
    result = subprocess.run(
        ["borg", "create", "--stats", "--compression", "lz4", archive, BACKUP_SOURCE],
        env=env, capture_output=True, text=True,
    )
    duration = int(time.time() - t0)
    now = datetime.now(timezone.utc)

    rpo = int((now - last_backup_time).total_seconds() / 60) if last_backup_time else 0

    if result.returncode == 0:
        compressed_bytes = get_compressed_size(archive)
        rto = estimate_rto(compressed_bytes, duration)
        size_bytes = compressed_bytes if compressed_bytes > 0 else None

        last_backup_time = now
        log.info(
            f"Backup OK duration={duration}s size={compressed_bytes//1024}KB "
            f"RPO={rpo}m RTO={rto}m"
        )
        report(
            "success",
            archive_name=archive,
            duration_sec=duration,
            size_bytes=size_bytes,
            rpo_minutes=rpo,
            rto_minutes=rto,
        )
    else:
        log.error(f"Backup FAILED: {result.stderr[:500]}")
        report("fail", archive_name=archive, error_msg=result.stderr[:500])


def main():
    log.info(f"BorgBackup service. repo={BORG_REPO} source={BACKUP_SOURCE}")
    init_repo()
    while True:
        do_backup()
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
