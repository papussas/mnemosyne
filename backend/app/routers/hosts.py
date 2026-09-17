from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ..authz import assert_in_scope, scoped_list_engagement
from ..db import get_session
from ..deps import Principal, current_reader, current_writer
from ..models import Asset, Engagement, Host
from ..schemas import HostCreate, HostUpdate

router = APIRouter(prefix="/hosts", tags=["hosts"])


def _link_asset(session: Session, client_id: int, ip: str, fqdn: str | None) -> Asset:
    """Find-or-create the client-scoped Asset for this host and bump last_seen."""
    stmt = select(Asset).where(Asset.client_id == client_id, Asset.ip == ip)
    asset = session.exec(stmt).first()
    if not asset and fqdn:
        asset = session.exec(
            select(Asset).where(Asset.client_id == client_id, Asset.fqdn == fqdn)
        ).first()
    if asset:
        asset.last_seen = datetime.utcnow()
        if fqdn and not asset.fqdn:
            asset.fqdn = fqdn
    else:
        asset = Asset(client_id=client_id, ip=ip, fqdn=fqdn)
    session.add(asset)
    session.flush()
    return asset


@router.get("")
def list_hosts(request: Request, limit: int = 500, offset: int = 0,
               session: Session = Depends(get_session), p: Principal = Depends(current_reader)):
    stmt = select(Host)
    req_eng = request.query_params.get("engagement_id")
    eng = scoped_list_engagement(p, int(req_eng) if req_eng else None)
    if eng is not None:
        stmt = stmt.where(Host.engagement_id == eng)
    aid = request.query_params.get("asset_id")
    if aid is not None:
        stmt = stmt.where(Host.asset_id == int(aid))
    ipf = request.query_params.get("ip")
    if ipf:
        stmt = stmt.where(Host.ip == ipf)
    return session.exec(stmt.order_by(Host.id.desc()).offset(offset).limit(min(limit, 2000))).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_host(body: HostCreate, session: Session = Depends(get_session),
                p: Principal = Depends(current_writer)):
    assert_in_scope(p, body.engagement_id)
    eng = session.get(Engagement, body.engagement_id)
    if not eng:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "engagement not found")
    # idempotent by (engagement, ip): enrich the existing host instead of duplicating
    existing = session.exec(select(Host).where(
        Host.engagement_id == body.engagement_id, Host.ip == body.ip)).first()
    if existing:
        d = body.model_dump(exclude_unset=True)
        for f in ("hostname", "os", "notes"):
            v = d.get(f)
            if v and not getattr(existing, f):
                setattr(existing, f, v)
        if body.tags:
            existing.tags = sorted(set((existing.tags or []) + body.tags))
        existing.updated_at = datetime.utcnow()
        session.add(existing); session.commit(); session.refresh(existing)
        return existing
    asset = _link_asset(session, eng.client_id, body.ip, body.hostname)
    host = Host(**body.model_dump(), asset_id=asset.id, author=p.actor)
    session.add(host); session.commit(); session.refresh(host)
    return host


@router.get("/{host_id}")
def get_host(host_id: int, session: Session = Depends(get_session),
             p: Principal = Depends(current_reader)):
    host = session.get(Host, host_id)
    if not host:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "host not found")
    assert_in_scope(p, host.engagement_id)
    return host


@router.patch("/{host_id}")
def update_host(host_id: int, body: HostUpdate, session: Session = Depends(get_session),
                p: Principal = Depends(current_writer)):
    host = session.get(Host, host_id)
    if not host:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "host not found")
    assert_in_scope(p, host.engagement_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(host, k, v)
    host.updated_at = datetime.utcnow()
    session.add(host); session.commit(); session.refresh(host)
    return host


@router.delete("/{host_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_host(host_id: int, session: Session = Depends(get_session),
                p: Principal = Depends(current_writer)):
    host = session.get(Host, host_id)
    if not host:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "host not found")
    assert_in_scope(p, host.engagement_id)
    session.delete(host); session.commit()
