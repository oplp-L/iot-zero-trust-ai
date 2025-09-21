import json
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.db import SessionLocal
from backend.app.models import RiskAction
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/risk/actions", tags=["risk"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RiskActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    score_id: Optional[int] = None
    action_type: str
    executed: Optional[bool] = None
    detail: Optional[Any] = None
    created_at: Optional[str] = None


@router.get("/{device_id}", response_model=List[RiskActionOut])
def list_actions(
    device_id: int,
    limit: int = Query(20, ge=1, le=100),
    raw: bool = Query(False),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(RiskAction)
        .filter(RiskAction.device_id == device_id)
        .order_by(RiskAction.id.desc())
        .limit(limit)
        .all()
    )
    result: List[RiskActionOut] = []
    for r in rows:
        detail_val = r.detail
        if not raw and isinstance(detail_val, str):
            try:
                detail_val = json.loads(detail_val)
            except Exception:
                pass
        # 不直接修改 r.detail，避免污染 ORM 状态
        result.append(
            RiskActionOut(
                id=r.id,
                device_id=r.device_id,
                score_id=r.score_id,
                action_type=r.action_type,
                executed=bool(r.executed),
                detail=detail_val,
                created_at=r.created_at.isoformat() if getattr(r, "created_at", None) else None,
            )
        )
    return result
