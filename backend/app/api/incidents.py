"""
Эндпоинты для управления инцидентами.
"""

import os
import subprocess
from fastapi import APIRouter, Request
from pydantic import BaseModel
from app.core.audit import (
    log_incident, log_audit,
    get_incidents, get_audit_log,
)
from app.core.limiter import limiter
from app.core.policy import determine_action

router = APIRouter(prefix="/incidents", tags=["incidents"])

WATCH_PATH = os.getenv("WATCH_PATH", "/monitored")


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


# Эндпоинты ниже объявлены как sync (def): SQLite-вызовы блокирующие,
# FastAPI выполняет их в threadpool, не задерживая event loop.

@router.post("/report", response_model=IncidentResponse)
@limiter.limit("60/minute")
def report_incident(request: Request, payload: IncidentIn):
    action, message = determine_action(payload.alert_count, payload.entropy)

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
def reset_lockdown():
    """
    Сбрасывает lockdown — восстанавливает права директории.
    Вызывается скриптом симуляции перед каждым тестом.
    """
    try:
        # chmod внутри контейнера backend (путь /monitored примонтирован)
        subprocess.run(
            ["chmod", "-R", "755", WATCH_PATH],
            check=False, capture_output=True
        )
        log_audit(
            event="LOCKDOWN_RESET",
            detail=f"Manual reset via API. path={WATCH_PATH}",
            host="api"
        )
        return {"status": "ok", "message": f"Lockdown reset. {WATCH_PATH} → 755"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/list")
def list_incidents(limit: int = 50):
    return get_incidents(limit)


@router.get("/audit")
def audit_log(limit: int = 100):
    return get_audit_log(limit)
