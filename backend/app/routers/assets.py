from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ..db import get_session
from ..deps import Principal, current_reader, current_writer
from ..schemas import AssetUpdate
from ..authz import agent_scope, asset_engagement_ids
from ..models import (Asset, Credential, CredentialWorksOn, Engagement, Finding,
                      Host, Service)

router = APIRouter(prefix="/assets", tags=["assets"])


def _guard_asset(p: Principal, session: Session, asset_id: int) -> None:
    scope = agent_scope(p)
    if scope is not None and scope not in asset_engagement_ids(session, asset_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "This API token is scoped to a different engagement")


def _as_bool(v):
    return v is not None and str(v).lower() in ("1", "true", "yes", "on")


@router.get("")
def list_assets(request: Request, session: Session = Depends(get_session),
                p: Principal = Depends(current_reader)):
    """Assets with per-asset counts, filterable by client, engagement, free text,
    and has_services / has_findings / has_creds."""
    qp = request.query_params
    stmt = select(Asset)
    if qp.get("client_id"):
        stmt = stmt.where(Asset.client_id == int(qp["client_id"]))
    assets = session.exec(stmt.order_by(Asset.id.desc())).all()

    q = (qp.get("q") or "").lower().strip()
    eng_filter = int(qp["engagement_id"]) if qp.get("engagement_id") else None
    want_svc, want_find, want_creds = _as_bool(qp.get("has_services")), _as_bool(qp.get("has_findings")), _as_bool(qp.get("has_creds"))

    out = []
    for a in assets:
        if q:
            hay = " ".join(filter(None, [a.ip, a.fqdn, a.label, a.notes])).lower()
            if q not in hay:
                continue
        hosts = session.exec(select(Host).where(Host.asset_id == a.id)).all()
        eng_ids = sorted({h.engagement_id for h in hosts})
        if eng_filter is not None and eng_filter not in eng_ids:
            continue
        scope = agent_scope(p)
        if scope is not None and scope not in eng_ids:
            continue
        host_ids = [h.id for h in hosts]
        services = session.exec(select(Service).where(Service.host_id.in_(host_ids))).all() if host_ids else []
        svc_ids = [s.id for s in services]
        n_find = len(session.exec(select(Finding).where(Finding.asset_id == a.id)).all())
        n_creds = 0
        if svc_ids:
            links = session.exec(select(CredentialWorksOn).where(CredentialWorksOn.service_id.in_(svc_ids))).all()
            n_creds = len({l.credential_id for l in links})
        counts = {"engagements": len(eng_ids), "services": len(services),
                  "findings": n_find, "credentials": n_creds}
        if (want_svc and not counts["services"]) or (want_find and not counts["findings"]) or (want_creds and not counts["credentials"]):
            continue
        d = a.model_dump()
        d["counts"] = counts
        d["engagement_ids"] = eng_ids
        out.append(d)
    return out


@router.patch("/{asset_id}")
def update_asset(asset_id: int, body: AssetUpdate, session: Session = Depends(get_session),
                 p: Principal = Depends(current_writer)):
    a = session.get(Asset, asset_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    _guard_asset(p, session, asset_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    session.add(a); session.commit(); session.refresh(a)
    return a


@router.get("/{asset_id}")
def get_asset(asset_id: int, session: Session = Depends(get_session),
              p: Principal = Depends(current_reader)):
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    _guard_asset(p, session, asset_id)
    return asset


@router.get("/{asset_id}/findings")
def asset_findings(asset_id: int, session: Session = Depends(get_session),
                   p: Principal = Depends(current_reader)):
    """All findings associated with this asset, across every engagement it appeared in."""
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    _guard_asset(p, session, asset_id)
    rows = session.exec(select(Finding).where(Finding.asset_id == asset_id)
                        .order_by(Finding.created_at.desc())).all()
    out = []
    for f in rows:
        eng = session.get(Engagement, f.engagement_id)
        svc = session.get(Service, f.service_id)
        out.append({
            "id": f.id, "title": f.title, "severity": f.severity, "status": f.status,
            "cve": f.cve, "created_at": f.created_at,
            "engagement_id": f.engagement_id, "engagement": eng.name if eng else None,
            "service": f"{svc.port}/{svc.proto} {svc.service_type}" if svc else None,
        })
    return out


@router.get("/{asset_id}/credentials")
def asset_credentials(asset_id: int, session: Session = Depends(get_session),
                      p: Principal = Depends(current_reader)):
    """Credentials that have been tested against any service on this asset (any engagement)."""
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    _guard_asset(p, session, asset_id)
    host_ids = [h.id for h in session.exec(select(Host).where(Host.asset_id == asset_id)).all()]
    if not host_ids:
        return []
    services = session.exec(select(Service).where(Service.host_id.in_(host_ids))).all()
    svc_map = {s.id: s for s in services}
    if not svc_map:
        return []
    links = session.exec(select(CredentialWorksOn)
                         .where(CredentialWorksOn.service_id.in_(list(svc_map)))).all()
    grouped: dict[int, list] = {}
    for link in links:
        grouped.setdefault(link.credential_id, []).append(link)
    out = []
    for cid, ls in grouped.items():
        cred = session.get(Credential, cid)
        if not cred:
            continue
        out.append({
            "credential": {"id": cred.id, "cred_type": cred.cred_type, "username": cred.username,
                           "realm": cred.realm, "validated": cred.validated, "source": cred.source,
                           "engagement_id": cred.engagement_id},
            "works_on": [{"service_id": l.service_id, "status": l.status,
                          "service": f"{svc_map[l.service_id].port}/{svc_map[l.service_id].proto}"
                                     if l.service_id in svc_map else None} for l in ls],
        })
    return out


@router.get("/{asset_id}/history")
def asset_history(asset_id: int, session: Session = Depends(get_session),
                  p: Principal = Depends(current_reader)):
    """Cross-engagement memory: every prior sighting of this box (same client),
    its services, and findings recorded against it."""
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    _guard_asset(p, session, asset_id)
    hosts = session.exec(select(Host).where(Host.asset_id == asset_id)
                         .order_by(Host.created_at.desc())).all()
    sightings = []
    for h in hosts:
        services = session.exec(select(Service).where(Service.host_id == h.id)).all()
        svc_ids = [s.id for s in services]
        findings = []
        if svc_ids:
            findings = session.exec(select(Finding).where(Finding.service_id.in_(svc_ids))).all()
        sightings.append({
            "host_id": h.id,
            "engagement_id": h.engagement_id,
            "seen_at": h.created_at,
            "hostname": h.hostname,
            "os": h.os,
            "services": [{"port": s.port, "proto": s.proto, "service_type": s.service_type,
                          "product": s.product, "version": s.version} for s in services],
            "findings": [{"id": f.id, "title": f.title, "severity": f.severity,
                          "status": f.status} for f in findings],
        })
    return {"asset": asset, "sightings": sightings}
