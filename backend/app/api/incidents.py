"""
Эндпоинты для управления инцидентами.
"""

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.core.audit import (
    log_incident, log_audit,
    get_incidents, get_audit_log,
)
from app.core.limiter import limiter
from app.core.policy import determine_action
from app.core.auth import require_token
from app.core.config import settings

router = APIRouter(prefix="/incidents", tags=["incidents"])


class IncidentIn(BaseModel):
    severity: str
    trigger_file: str
    entropy: float
    alert_count: int
    host: str = "unknown"
    # eBPF: запись в файл с ransomware-расширением (.locked, .enc, ...)
    suspicious_ext: bool = False


class IncidentResponse(BaseModel):
    incident_id: int
    action: str
    message: str


# Эндпоинты ниже объявлены как sync (def): SQLite-вызовы блокирующие,
# FastAPI выполняет их в threadpool, не задерживая event loop.

@router.post("/report", response_model=IncidentResponse,
             dependencies=[Depends(require_token)])
@limiter.limit("60/minute")
def report_incident(request: Request, payload: IncidentIn):
    action, message = determine_action(
        payload.alert_count, payload.entropy, payload.suspicious_ext
    )

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


@router.post("/reset-lockdown", dependencies=[Depends(require_token)])
def reset_lockdown():
    """
    Сбрасывает lockdown. Файловой системой /monitored владеет АГЕНТ
    (он на хосте, у него mount и права), поэтому backend не трогает FS сам,
    а форвардит команду на control-сервер агента. Это убирает архитектурный
    костыль «backend лезет в чужую файловую систему».
    """
    headers = {"Authorization": f"Bearer {settings.rg_token}"} if settings.rg_token else {}
    try:
        r = httpx.post(f"{settings.agent_url}/release", headers=headers, timeout=5.0)
        log_audit(
            event="LOCKDOWN_RESET",
            detail=f"Forwarded to agent {settings.agent_url}, status={r.status_code}",
            host="api",
        )
        return {"status": "ok", "message": "Release command forwarded to agent"}
    except Exception as e:
        log_audit(event="LOCKDOWN_RESET_FAIL", detail=str(e), host="api")
        return {"status": "error", "message": str(e)}


@router.get("/list")
def list_incidents(limit: int = 50):
    return get_incidents(limit)


@router.get("/audit")
def audit_log(limit: int = 100):
    return get_audit_log(limit)
