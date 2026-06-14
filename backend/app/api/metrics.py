from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
from typing import List

from app.core.database import get_db
from app.core.limiter import limiter
from app.core.auth import require_token
from app.schemas.metrics import (
    EntropyMetricIn, EntropyMetricOut,
    BackupEventIn, BackupEventOut,
    SystemMetricIn, AlertSummary,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.post("/entropy", status_code=201, dependencies=[Depends(require_token)])
@limiter.limit("300/minute")
async def ingest_entropy(request: Request, payload: EntropyMetricIn, db: AsyncSession = Depends(get_db)):
    await db.execute(text(
        "INSERT INTO entropy_metrics (file_path, entropy, file_size, alert, host) "
        "VALUES (:file_path, :entropy, :file_size, :alert, :host)"
    ), payload.model_dump())
    await db.commit()
    return {"status": "ok"}


@router.get("/entropy", response_model=List[EntropyMetricOut])
async def get_entropy(
    minutes: int = Query(60, ge=1, le=1440),
    alert_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    where = "WHERE time >= :since" + (" AND alert = TRUE" if alert_only else "")
    result = await db.execute(
        text(f"SELECT * FROM entropy_metrics {where} ORDER BY time DESC LIMIT 1000"),
        {"since": since},
    )
    return result.mappings().all()


@router.post("/backup", status_code=201, dependencies=[Depends(require_token)])
@limiter.limit("60/minute")
async def ingest_backup_event(request: Request, payload: BackupEventIn, db: AsyncSession = Depends(get_db)):
    await db.execute(text(
        "INSERT INTO backup_events "
        "(event_type, archive_name, duration_sec, size_bytes, rpo_minutes, rto_minutes, error_msg) "
        "VALUES (:event_type, :archive_name, :duration_sec, :size_bytes, :rpo_minutes, :rto_minutes, :error_msg)"
    ), payload.model_dump())
    await db.commit()
    return {"status": "ok"}


@router.get("/backup", response_model=List[BackupEventOut])
async def get_backup_events(limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT * FROM backup_events ORDER BY time DESC LIMIT :limit"),
        {"limit": limit},
    )
    return result.mappings().all()


@router.post("/system", status_code=201, dependencies=[Depends(require_token)])
@limiter.limit("120/minute")
async def ingest_system(request: Request, payload: SystemMetricIn, db: AsyncSession = Depends(get_db)):
    await db.execute(text(
        "INSERT INTO system_metrics (cpu_pct, mem_pct, disk_pct, net_in_kb, net_out_kb) "
        "VALUES (:cpu_pct, :mem_pct, :disk_pct, :net_in_kb, :net_out_kb)"
    ), payload.model_dump())
    await db.commit()
    return {"status": "ok"}


@router.get("/system")
async def get_system(minutes: int = Query(30, ge=1, le=1440), db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    result = await db.execute(
        text("SELECT * FROM system_metrics WHERE time >= :since ORDER BY time DESC LIMIT 500"),
        {"since": since},
    )
    return result.mappings().all()


@router.get("/summary", response_model=AlertSummary)
async def get_summary(db: AsyncSession = Depends(get_db)):
    since_1h  = datetime.now(timezone.utc) - timedelta(hours=1)
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    # Окно 24ч — счётчик за всю жизнь БД бессмысленен на дашборде
    alerts = await db.execute(text(
        "SELECT COUNT(*) as cnt, MAX(time) as last_time FROM entropy_metrics "
        "WHERE alert = TRUE AND time >= :since"
    ), {"since": since_24h})
    alert_row = alerts.mappings().one()
    avg_e = await db.execute(
        text("SELECT AVG(entropy) as avg_e FROM entropy_metrics WHERE time >= :since"),
        {"since": since_1h},
    )
    avg_entropy = avg_e.scalar()
    # time <= now() отсекает записи «из будущего» (рассинхрон часов в момент
    # вставки): иначе будущая метка выигрывает ORDER BY time DESC и подменяет
    # реальный последний бэкап, а на дашборде получается «-N с назад».
    last_bk = await db.execute(text(
        "SELECT time, rpo_minutes, rto_minutes FROM backup_events "
        "WHERE event_type = 'success' AND time <= now() ORDER BY time DESC LIMIT 1"
    ))
    bk_row = last_bk.mappings().one_or_none()
    return AlertSummary(
        total_alerts=alert_row["cnt"] or 0,
        last_alert_time=alert_row["last_time"],
        avg_entropy_1h=round(avg_entropy, 4) if avg_entropy else None,
        last_backup=bk_row["time"] if bk_row else None,
        rpo_minutes=bk_row["rpo_minutes"] if bk_row else None,
        rto_minutes=bk_row["rto_minutes"] if bk_row else None,
    )
