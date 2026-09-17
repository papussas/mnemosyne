"""Engagement activity feed ("inbox") — a read-model that merges recent changes
across the engagement so a human or agent can pull "what's new since I last looked".
Poll with the returned `cursor` as `since`; `exclude_actor` hides your own actions."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..authz import assert_in_scope
from ..db import get_session
from ..deps import Principal, current_reader
from ..models import (Attachment, Credential, CredentialWorksOn, Engagement,
                      Evidence, Finding, Host, Loot, Service)

router = APIRouter(tags=["activity"])


def _ts(obj):
    return getattr(obj, "updated_at", None) or obj.created_at


def _action(obj) -> str:
    u = getattr(obj, "updated_at", None)
    c = getattr(obj, "created_at", None)
    return "update" if (u and c and (u - c).total_seconds() > 1) else "create"


@router.get("/engagements/{engagement_id}/activity")
def activity(engagement_id: int, since: str = "", limit: int = 100,
             exclude_actor: str = "", session: Session = Depends(get_session),
             p: Principal = Depends(current_reader)):
    if not session.get(Engagement, engagement_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "engagement not found")
    assert_in_scope(p, engagement_id)

    cutoff: Optional[datetime] = None
    if since:
        try:
            cutoff = datetime.fromisoformat(since.replace("Z", ""))
        except ValueError:
            cutoff = None

    hosts = session.exec(select(Host).where(Host.engagement_id == engagement_id)).all()
    host_ids = [h.id for h in hosts]; host_map = {h.id: h for h in hosts}
    services = session.exec(select(Service).where(Service.host_id.in_(host_ids))).all() if host_ids else []
    svc_ids = [s.id for s in services]; svc_map = {s.id: s for s in services}
    findings = session.exec(select(Finding).where(Finding.engagement_id == engagement_id)).all()
    find_ids = [f.id for f in findings]
    creds = session.exec(select(Credential).where(Credential.engagement_id == engagement_id)).all()
    cred_ids = [c.id for c in creds]; cred_map = {c.id: c for c in creds}
    loot = session.exec(select(Loot).where(Loot.engagement_id == engagement_id)).all()
    loot_ids = [lo.id for lo in loot]
    evidence = [e for e in session.exec(select(Evidence)).all()
                if e.finding_id in find_ids or e.service_id in svc_ids or e.host_id in host_ids]
    ev_ids = [e.id for e in evidence]
    works = session.exec(select(CredentialWorksOn).where(CredentialWorksOn.credential_id.in_(cred_ids))).all() if cred_ids else []

    def att_in(a):
        return ((a.target_type == "finding" and a.target_id in find_ids) or
                (a.target_type == "service" and a.target_id in svc_ids) or
                (a.target_type == "host" and a.target_id in host_ids) or
                (a.target_type == "evidence" and a.target_id in ev_ids) or
                (a.target_type == "loot" and a.target_id in loot_ids))
    atts = [a for a in session.exec(select(Attachment)).all() if att_in(a)]

    ev: list[dict] = []
    def add(ts, actor, kind, action, summary, ref):
        ev.append({"ts": ts, "actor": actor, "kind": kind, "action": action,
                   "summary": summary, "ref": ref})

    for h in hosts:
        add(_ts(h), h.author, "host", _action(h),
            f"host {h.ip}" + (f" ({h.hostname})" if h.hostname else ""), {"host_id": h.id})
    for s in services:
        hh = host_map.get(s.host_id)
        add(_ts(s), s.author, "service", _action(s),
            f"service {s.port}/{s.proto} {s.service_type} on {hh.ip if hh else '?'}",
            {"service_id": s.id, "host_id": s.host_id})
    for f in findings:
        add(_ts(f), f.author, "finding", _action(f),
            f"finding [{f.severity}] {f.title or 'finding'} ({f.status})",
            {"finding_id": f.id, "service_id": f.service_id})
    for c in creds:
        add(_ts(c), c.author, "secret", _action(c),
            f"secret {c.username or ''} ({c.cred_type})" + (" [validated]" if c.validated else ""),
            {"credential_id": c.id})
    for w in works:
        s = svc_map.get(w.service_id); cr = cred_map.get(w.credential_id)
        add(w.created_at, w.author, "cred-result", "create",
            f"secret {cr.username if cr else w.credential_id} {w.status} on "
            f"{(str(s.port) + '/' + s.proto) if s else w.service_id}",
            {"credential_id": w.credential_id, "service_id": w.service_id, "status": w.status})
    for e in evidence:
        add(_ts(e), e.author, "evidence", _action(e), f"evidence: {e.title}",
            {"evidence_id": e.id, "finding_id": e.finding_id, "service_id": e.service_id})
    for a in atts:
        kind = "screenshot" if (a.mime or "").startswith("image/") else "file"
        add(a.created_at, a.author, "attachment", "create",
            f"{kind} added to {a.target_type} #{a.target_id}",
            {"attachment_id": a.id, "target_type": a.target_type, "target_id": a.target_id})
    for lo in loot:
        add(_ts(lo), lo.author, "loot", _action(lo), f"loot: {lo.title}", {"loot_id": lo.id})

    filtered = [e for e in ev
                if (cutoff is None or e["ts"] > cutoff)
                and not (exclude_actor and e["actor"] == exclude_actor)]
    filtered.sort(key=lambda e: e["ts"])            # oldest first for correct forward paging
    total = len(filtered)
    lim = min(max(limit, 1), 500)
    page = filtered[:lim]
    cursor = page[-1]["ts"].isoformat() if page else (since or None)
    for e in page:
        e["ts"] = e["ts"].isoformat()
    page.reverse()                                   # present newest first
    return {"engagement_id": engagement_id, "cursor": cursor,
            "count": len(page), "has_more": total > lim, "events": page}
