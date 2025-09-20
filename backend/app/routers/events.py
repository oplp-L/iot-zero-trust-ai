from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, UTC

from ..db import SessionLocal
from .. import auth
from ..models import Device, User, DeviceEvent
from ..schemas_ai import EventIngestBatch

router = APIRouter(prefix="/events", tags=["Events"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/ingest", summary="批量上报设备事件")
def ingest_events(
    batch: EventIngestBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    device_ids = {e.device_id for e in batch.events}
    if current_user.role != "admin":
        owned = {
            d.id for d in db.query(Device)
            .filter(Device.owner_id == current_user.id, Device.id.in_(device_ids))
            .all()
        }
        if owned != device_ids:
            raise HTTPException(status_code=403, detail="One or more devices not owned by user")

    now = datetime.now(UTC)
    rows = []
    for ev in batch.events:
        # 统一将 ts 转为 UTC aware
        if ev.ts is None:
            ts = now
        else:
            ts = ev.ts
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            else:
                ts = ts.astimezone(UTC)

        rows.append(DeviceEvent(
            device_id=ev.device_id,
            event_type=ev.event_type,
            ts=ts,
            payload=ev.payload
        ))
    db.add_all(rows)
    db.commit()
    return {"ingested": len(rows)}