from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ..db import get_session
from ..deps import Principal, current_reader, current_writer
from ..authz import assert_in_scope, scoped_list_engagement
from ..models import Claim
from ..schemas import ClaimCreate

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("")
def list_claims(request: Request, active_only: bool = False,
                session: Session = Depends(get_session), p: Principal = Depends(current_reader)):
    stmt = select(Claim)
    eid = request.query_params.get("engagement_id")
    eng = scoped_list_engagement(p, int(eid) if eid else None)
    if eng is not None:
        stmt = stmt.where(Claim.engagement_id == eng)
    rows = session.exec(stmt.order_by(Claim.id.desc())).all()
    now = datetime.utcnow()
    result = []
    for c in rows:
        active = (not c.released) and c.expires_at > now
        if active_only and not active:
            continue
        d = c.model_dump()
        d["active"] = active
        result.append(d)
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_claim(body: ClaimCreate, session: Session = Depends(get_session),
                 p: Principal = Depends(current_writer)):
    assert_in_scope(p, body.engagement_id)
    now = datetime.utcnow()
    existing = session.exec(
        select(Claim).where(Claim.engagement_id == body.engagement_id,
                            Claim.target == body.target, Claim.released == False)  # noqa: E712
    ).all()
    for c in existing:
        if c.expires_at > now:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"target already claimed by {c.claimed_by} until {c.expires_at.isoformat()}")
    claim = Claim(engagement_id=body.engagement_id, target=body.target,
                  claimed_by=p.actor, expires_at=now + timedelta(minutes=body.ttl_minutes))
    session.add(claim); session.commit(); session.refresh(claim)
    return claim


@router.delete("/{claim_id}")
def release_claim(claim_id: int, session: Session = Depends(get_session),
                  p: Principal = Depends(current_writer)):
    claim = session.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "claim not found")
    assert_in_scope(p, claim.engagement_id)
    claim.released = True
    session.add(claim); session.commit()
    return {"ok": True, "released": True}
