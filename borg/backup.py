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
    rto = int(duration * 1.2 / 60) + 1
    if result.returncode == 0:
        last_backup_time = now
        log.info(f"Backup OK duration={duration}s RPO={rpo}m RTO={rto}m")
        report("success", archive_name=archive, duration_sec=duration,
               rpo_minutes=rpo, rto_minutes=rto)
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
