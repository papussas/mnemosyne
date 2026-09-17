"""Engagement coverage / progress metrics."""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..authz import assert_in_scope
from ..db import get_session
from ..deps import Principal, current_reader
from ..models import Credential, Engagement, Finding, Host, Scope, Service

router = APIRouter(tags=["coverage"])


@router.get("/engagements/{eid}/coverage")
def coverage(eid: int, session: Session = Depends(get_session),
             p: Principal = Depends(current_reader)):
    if not session.get(Engagement, eid):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "engagement not found")
    assert_in_scope(p, eid)

    hosts = session.exec(select(Host).where(Host.engagement_id == eid)).all()
    host_ids = [h.id for h in hosts]
    services = session.exec(select(Service).where(Service.host_id.in_(host_ids))).all() if host_ids else []
    findings = session.exec(select(Finding).where(Finding.engagement_id == eid)).all()
    creds = session.exec(select(Credential).where(Credential.engagement_id == eid)).all()
    scope = session.exec(select(Scope).where(Scope.engagement_id == eid)).all()

    hosts_with_svc = {s.host_id for s in services}
    svc_with_find = {f.service_id for f in findings}
    return {
        "hosts": {
            "total": len(hosts),
            "in_scope": sum(1 for h in hosts if h.in_scope),
            "with_services": len(hosts_with_svc),
            "without_services": len(hosts) - len(hosts_with_svc),
        },
        "services": {
            "total": len(services),
            "with_findings": len(svc_with_find),
            "without_findings": len(services) - len(svc_with_find),
        },
        "findings": {
            "total": len(findings),
            "by_severity": dict(Counter(f.severity for f in findings)),
            "by_status": dict(Counter(f.status for f in findings)),
        },
        "secrets": {
            "total": len(creds),
            "validated": sum(1 for c in creds if c.validated),
        },
        "scope_rules": len(scope),
    }
