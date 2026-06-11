from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional


class EntropyMetricIn(BaseModel):
    file_path: str
    entropy: float = Field(..., ge=0.0, le=8.0)
    file_size: Optional[int] = None
    alert: bool = False
    host: str = "localhost"


class EntropyMetricOut(BaseModel):
    time: datetime
    file_path: str
    entropy: float
    file_size: Optional[int]
    alert: bool
    host: str

    class Config:
        from_attributes = True


class BackupEventIn(BaseModel):
    event_type: Literal["start", "success", "fail"]
    archive_name: Optional[str] = None
    duration_sec: Optional[int] = None
    size_bytes: Optional[int] = None
    rpo_minutes: Optional[int] = None
    rto_minutes: Optional[int] = None
    error_msg: Optional[str] = None


class BackupEventOut(BaseModel):
    time: datetime
    event_type: str
    archive_name: Optional[str]
    duration_sec: Optional[int]
    size_bytes: Optional[int]
    rpo_minutes: Optional[int]
    rto_minutes: Optional[int]
    error_msg: Optional[str]

    class Config:
        from_attributes = True


class SystemMetricIn(BaseModel):
    cpu_pct: float
    mem_pct: float
    disk_pct: float
    net_in_kb: float = 0.0
    net_out_kb: float = 0.0


class AlertSummary(BaseModel):
    total_alerts: int
    last_alert_time: Optional[datetime]
    avg_entropy_1h: Optional[float]
    last_backup: Optional[datetime]
    rpo_minutes: Optional[int]
    rto_minutes: Optional[int]
