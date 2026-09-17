from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ..db import get_session
from ..deps import Principal, current_reader, current_writer
from ..authz import agent_scope, assert_in_scope, evidence_engagement
from ..integrity import canonical_hash, record
from ..models import Evidence
from ..schemas import EvidenceCreate, EvidenceUpdate

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("")
def list_evidence(request: Request, session: Session = Depends(get_session),
                  p: Principal = Depends(current_reader)):
    stmt = select(Evidence)
    for f in ("host_id", "service_id", "finding_id"):
        v = request.query_params.get(f)
        if v is not None:
            stmt = stmt.where(getattr(Evidence, f) == int(v))
    rows = session.exec(stmt.order_by(Evidence.id.desc())).all()
    scope = agent_scope(p)
    if scope is not None:
        rows = [e for e in rows if evidence_engagement(session, e) == scope]
    return rows


@router.post("", status_code=status.HTTP_201_CREATED)
def create_evidence(body: EvidenceCreate, session: Session = Depends(get_session),
                    p: Principal = Depends(current_writer)):
    ev = Evidence(**body.model_dump(), author=p.actor)
    assert_in_scope(p, evidence_engagement(session, ev))
    session.add(ev); session.flush()  # assign id before hashing
    ev.content_hash = canonical_hash(ev.model_dump())
    record(session, actor=p.actor, action="create", entity_type="evidence",
           entity_id=ev.id, snapshot=ev.model_dump())
    session.commit(); session.refresh(ev)
    return ev


@router.get("/{ev_id}")
def get_evidence(ev_id: int, session: Session = Depends(get_session),
                 p: Principal = Depends(current_reader)):
    ev = session.get(Evidence, ev_id)
    if not ev:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "evidence not found")
    assert_in_scope(p, evidence_engagement(session, ev))
    return ev


@router.patch("/{ev_id}")
def update_evidence(ev_id: int, body: EvidenceUpdate, session: Session = Depends(get_session),
                    p: Principal = Depends(current_writer)):
    ev = session.get(Evidence, ev_id)
    if not ev:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "evidence not found")
    assert_in_scope(p, evidence_engagement(session, ev))
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ev, k, v)
    ev.updated_at = datetime.utcnow()
    ev.content_hash = canonical_hash(ev.model_dump())
    session.add(ev); session.flush()
    record(session, actor=p.actor, action="update", entity_type="evidence",
           entity_id=ev.id, snapshot=ev.model_dump())
    session.commit(); session.refresh(ev)
    return ev


@router.delete("/{ev_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(ev_id: int, session: Session = Depends(get_session),
                    p: Principal = Depends(current_writer)):
    ev = session.get(Evidence, ev_id)
    if not ev:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "evidence not found")
    assert_in_scope(p, evidence_engagement(session, ev))
    record(session, actor=p.actor, action="delete", entity_type="evidence",
           entity_id=ev.id, snapshot=ev.model_dump())
    session.delete(ev); session.commit()
