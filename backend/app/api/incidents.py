"""
Эндпоинты для управления инцидентами.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.core.audit import (
    init_db, log_incident, log_audit,
    get_incidents, get_audit_log,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])

init_db()


class IncidentIn(BaseModel):
    severity: str
    trigger_file: str
    entropy: float
    alert_count: int
    host: str = "unknown"


class IncidentResponse(BaseModel):
    incident_id: int
    action: str
    message: str


@router.post("/report", response_model=IncidentResponse)
async def report_incident(payload: IncidentIn):
    if payload.alert_count >= 10 or payload.entropy >= 7.9:
        action = "lockdown"
        message = "CRITICAL: lockdown initiated, emergency backup triggered"
    elif payload.alert_count >= 3:
        action = "emergency_backup"
        message = "WARNING: emergency backup triggered"
    else:
        action = "logged"
        message = "INFO: incident logged"

    incident_id = log_incident(
        severity=payload.severity,
        trigger_file=payload.trigger_file,
        entropy=payload.entropy,
        alert_count=payload.alert_count,
        action_taken=action,
        host=payload.host,
    )

    log_audit(
        event=f"INCIDENT_{action.upper()}",
        detail=f"file={payload.trigger_file} entropy={payload.entropy:.4f} alerts={payload.alert_count}",
        host=payload.host,
    )

    return IncidentResponse(
        incident_id=incident_id,
        action=action,
        message=message,
    )


@router.post("/reset-lockdown")
async def reset_lockdown():
    """Сбрасывает lockdown — разблокирует директорию для новых тестов."""
    import subprocess
    import os

    watch_path = os.getenv("WATCH_PATH", "/monitored")

    log_audit(event="LOCKDOWN_RESET", detail="Manual reset via API", host="api")

    return {"status": "ok", "message": f"Lockdown reset. {watch_path} unlocked."}


@router.get("/list")
async def list_incidents(limit: int = 50):
    return get_incidents(limit)


@router.get("/audit")
async def audit_log(limit: int = 100):
    return get_audit_log(limit)
