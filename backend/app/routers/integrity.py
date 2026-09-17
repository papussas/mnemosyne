from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ..db import get_session
from ..deps import Principal, current_reader
from ..integrity import canonical_hash, verify_chain
from ..models import AuditLog, Evidence, Finding

router = APIRouter(prefix="/integrity", tags=["integrity"])
_MODELS = {"finding": Finding, "evidence": Evidence}


@router.get("/verify")
def verify(session: Session = Depends(get_session), _: Principal = Depends(current_reader)):
    """Re-walk the whole audit ledger and report whether the hash chain is intact."""
    return verify_chain(session)


@router.get("/audit")
def audit(request: Request, limit: int = 500, session: Session = Depends(get_session),
          _: Principal = Depends(current_reader)):
    stmt = select(AuditLog)
    et = request.query_params.get("entity_type")
    eid = request.query_params.get("entity_id")
    if et:
        stmt = stmt.where(AuditLog.entity_type == et)
    if eid:
        stmt = stmt.where(AuditLog.entity_id == int(eid))
    return session.exec(stmt.order_by(AuditLog.id.desc()).limit(min(limit, 2000))).all()


@router.get("/check/{entity_type}/{entity_id}")
def check_record(entity_type: str, entity_id: int, session: Session = Depends(get_session),
                 _: Principal = Depends(current_reader)):
    """Point check: does the live record still hash to its stored content_hash and
    to the latest ledger entry's data_hash?"""
    model = _MODELS.get(entity_type)
    if not model:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"entity_type must be one of {sorted(_MODELS)}")
    obj = session.get(model, entity_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "record not found")
    live = canonical_hash(obj.model_dump())
    last = session.exec(
        select(AuditLog).where(AuditLog.entity_type == entity_type,
                              AuditLog.entity_id == entity_id)
        .order_by(AuditLog.id.desc()).limit(1)
    ).first()
    return {
        "entity_type": entity_type, "entity_id": entity_id,
        "stored_content_hash": obj.content_hash,
        "recomputed_hash": live,
        "content_hash_ok": obj.content_hash == live,
        "ledger_data_hash": last.data_hash if last else None,
        "ledger_match": bool(last and last.data_hash == live),
    }
