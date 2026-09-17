from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ..db import get_session
from ..deps import Principal, current_reader, current_writer
from ..authz import assert_in_scope, scoped_list_engagement
from ..integrity import canonical_hash, record
from ..models import Asset, Finding, FindingTemplate, Host, Service
from ..schemas import FindingCreate, FindingUpdate

router = APIRouter(prefix="/findings", tags=["findings"])


def _effective(session: Session, f: Finding) -> dict:
    """Merge template-inherited narrative for reads (instance overrides template)."""
    d = f.model_dump()
    tpl = session.get(FindingTemplate, f.template_id) if f.template_id else None
    d["effective_title"] = f.title or (tpl.title if tpl else None)
    d["effective_description"] = f.description or (tpl.description if tpl else None)
    d["effective_business_impact"] = f.business_impact or (tpl.business_impact if tpl else None)
    d["effective_remediation"] = f.remediation or (tpl.remediation if tpl else None)
    # affected asset context (both directions of the finding<->asset link)
    svc = session.get(Service, f.service_id)
    host = session.get(Host, svc.host_id) if svc else None
    asset = session.get(Asset, f.asset_id or (host.asset_id if host else None)) if (f.asset_id or host) else None
    d["host"] = {"id": host.id, "ip": host.ip, "hostname": host.hostname} if host else None
    d["asset"] = {"id": asset.id, "ip": asset.ip, "fqdn": asset.fqdn, "label": asset.label} if asset else None
    d["affected"] = (host.hostname or host.ip) if host else None
    return d


@router.get("")
def list_findings(request: Request, limit: int = 1000, offset: int = 0,
                  summary: bool = False, session: Session = Depends(get_session),
                  p: Principal = Depends(current_reader)):
    """List findings. `summary=true` returns a compact projection (no template/host/
    asset joins) — much smaller, for agents/large engagements. `limit` (max 5000) +
    `offset` paginate."""
    stmt = select(Finding)
    req_eng = request.query_params.get("engagement_id")
    eng = scoped_list_engagement(p, int(req_eng) if req_eng else None)
    if eng is not None:
        stmt = stmt.where(Finding.engagement_id == eng)
    for f in ("service_id", "asset_id", "severity", "status", "template_id"):
        v = request.query_params.get(f)
        if v is not None:
            col = getattr(Finding, f)
            stmt = stmt.where(col == (int(v) if v.isdigit() else v))
    stmt = stmt.order_by(Finding.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 5000))
    rows = session.exec(stmt).all()
    if summary:
        return [{"id": f.id, "engagement_id": f.engagement_id, "service_id": f.service_id,
                 "asset_id": f.asset_id, "title": f.title, "severity": f.severity,
                 "status": f.status, "cve": f.cve, "created_at": f.created_at.isoformat()}
                for f in rows]
    return [_effective(session, f) for f in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_finding(body: FindingCreate, session: Session = Depends(get_session),
                   p: Principal = Depends(current_writer)):
    assert_in_scope(p, body.engagement_id)
    svc = session.get(Service, body.service_id)
    if not svc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "service (anchor) not found")
    host = session.get(Host, svc.host_id)
    if host and host.engagement_id != body.engagement_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "service belongs to a different engagement than given")
    if not (body.title or body.template_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "finding needs a title or a template_id to inherit from")
    data = body.model_dump()
    data["severity"] = body.severity.value
    data["status"] = body.status.value
    data["asset_id"] = host.asset_id if host else None  # link finding to the cross-engagement asset
    f = Finding(**data, author=p.actor)
    session.add(f); session.flush()  # assign id before hashing
    f.content_hash = canonical_hash(f.model_dump())
    record(session, actor=p.actor, action="create", entity_type="finding",
           entity_id=f.id, snapshot=f.model_dump())
    session.commit(); session.refresh(f)
    return _effective(session, f)


@router.get("/{fid}")
def get_finding(fid: int, session: Session = Depends(get_session),
                p: Principal = Depends(current_reader)):
    f = session.get(Finding, fid)
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "finding not found")
    assert_in_scope(p, f.engagement_id)
    return _effective(session, f)


@router.patch("/{fid}")
def update_finding(fid: int, body: FindingUpdate, session: Session = Depends(get_session),
                   p: Principal = Depends(current_writer)):
    f = session.get(Finding, fid)
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "finding not found")
    assert_in_scope(p, f.engagement_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(f, k, v.value if hasattr(v, "value") else v)
    f.updated_at = datetime.utcnow()
    f.content_hash = canonical_hash(f.model_dump())
    session.add(f); session.flush()
    record(session, actor=p.actor, action="update", entity_type="finding",
           entity_id=f.id, snapshot=f.model_dump())
    session.commit(); session.refresh(f)
    return _effective(session, f)


@router.delete("/{fid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_finding(fid: int, session: Session = Depends(get_session),
                   p: Principal = Depends(current_writer)):
    f = session.get(Finding, fid)
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "finding not found")
    assert_in_scope(p, f.engagement_id)
    record(session, actor=p.actor, action="delete", entity_type="finding",
           entity_id=f.id, snapshot=f.model_dump())
    session.delete(f); session.commit()
