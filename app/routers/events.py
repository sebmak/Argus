import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
import json

from ..db.database import (
    get_event_logs,
    clear_event_logs,
    get_event_log_summary,
    record_event_log
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/events", tags=["Event Logs"])

# ==============================================================================
# Rules for ClearLogsRequest:
# 1. Variables and data schema properties must be declared at the top of the class.
# 2. Encapsulates optional filtering criteria when clearing operational logs.
# ==============================================================================
class ClearLogsRequest(BaseModel):
    category: Optional[str] = Field(None, description="Category filter to clear ('all', 'motion', 'detection', etc.)")
    before_date: Optional[str] = Field(None, description="Clear logs older than ISO date/time string")

@router.get("/logs")
async def list_event_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None, description="Filter by category ('motion', 'detection', 'webhook', 'mqtt', 'error', 'system')"),
    level: Optional[str] = Query(None, description="Filter by log level ('info', 'success', 'warning', 'error')"),
    search: Optional[str] = Query(None, description="Keyword search in messages and payload details")
) -> Dict[str, Any]:
    """Retrieves paginated and filtered system event logs."""
    data = get_event_logs(
        limit=limit,
        offset=offset,
        category=category,
        level=level,
        search=search
    )
    return {
        "total": data["total"],
        "count": len(data["logs"]),
        "limit": limit,
        "offset": offset,
        "logs": data["logs"]
    }

@router.get("/summary")
async def event_telemetry_summary() -> Dict[str, Any]:
    """Retrieves operational telemetry summary counts for the Event Log view."""
    return get_event_log_summary()

@router.delete("/logs")
async def delete_event_logs(payload: Optional[ClearLogsRequest] = None) -> Dict[str, Any]:
    """Clears matching or all operational event logs."""
    category = payload.category if payload else None
    before_date = payload.before_date if payload else None
    deleted = clear_event_logs(category=category, before_date=before_date)
    record_event_log(
        level="warning",
        category="system",
        event_type="logs_cleared",
        message=f"Event logs cleared ({deleted} entries removed)",
        details={"category": category, "before_date": before_date, "deleted": deleted}
    )
    return {
        "status": "success",
        "deleted_count": deleted
    }

@router.get("/export")
async def export_logs_json(
    category: Optional[str] = None,
    level: Optional[str] = None
):
    """Exports event logs as downloadable JSON file."""
    data = get_event_logs(limit=5000, offset=0, category=category, level=level)
    content = json.dumps(data["logs"], indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=faceengine-events.json"}
    )
