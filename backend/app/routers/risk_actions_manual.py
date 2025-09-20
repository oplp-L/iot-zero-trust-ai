from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db import SessionLocal
from backend.app.models import Device, RiskAction, DeviceLog

router = APIRouter(prefix="/risk/manual", tags=["risk"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/restore/{device_id}")
def manual_restore(device_id: int, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(404, "Device not found")
    if not hasattr(dev, "status"):
        raise HTTPException(400, "Device has no status field")
    if dev.status != "isolated":
        return {"message": "Device not isolated. No action."}

    # 写动作
    ra = RiskAction(
        device_id=device_id,
        score_id=None,
        action_type="restore",
        executed=True,
        detail={"mode": "manual"}
    )
    dev.status = "online"
    db.add(ra)
    db.add(DeviceLog(
        device_id=device_id,
        log_type="risk_alert",
        message="Manual restore executed"
    ))
    db.commit()
    return {"message": "Restored", "action_id": ra.id}