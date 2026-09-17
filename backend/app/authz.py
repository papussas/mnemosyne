"""Agent-token engagement-scope enforcement.

Human accounts (admin/contributor) are global. An *agent* API token may carry an
engagement_id; when it does, that token may only touch data in that engagement.
Unscoped tokens (engagement_id is None) behave like their human role.
"""
from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session

from .deps import Principal
from .models import Host


def agent_scope(p: Principal) -> Optional[int]:
    return p.engagement_id if getattr(p, "kind", None) == "agent" else None


def assert_in_scope(p: Principal, engagement_id: Optional[int]) -> None:
    """Raise 403 if a scoped agent token targets a different engagement."""
    scope = agent_scope(p)
    if scope is None:
        return
    if engagement_id is None or int(engagement_id) != int(scope):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "This API token is scoped to a different engagement")


def scoped_list_engagement(p: Principal, requested: Optional[int]) -> Optional[int]:
    """For list endpoints: clamp the engagement filter to a scoped token's engagement."""
    scope = agent_scope(p)
    if scope is None:
        return requested
    if requested is not None and int(requested) != int(scope):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "This API token is scoped to a different engagement")
    return scope


def host_engagement(session: Session, host_id: Optional[int]) -> Optional[int]:
    if host_id is None:
        return None
    h = session.get(Host, host_id)
    return h.engagement_id if h else None


def service_engagement(session: Session, service_id: Optional[int]) -> Optional[int]:
    from .models import Service
    if service_id is None:
        return None
    s = session.get(Service, service_id)
    return host_engagement(session, s.host_id) if s else None


def evidence_engagement(session: Session, ev) -> Optional[int]:
    from .models import Finding
    if ev.finding_id:
        f = session.get(Finding, ev.finding_id)
        if f:
            return f.engagement_id
    if ev.service_id:
        return service_engagement(session, ev.service_id)
    return host_engagement(session, ev.host_id)


def attachment_target_engagement(session: Session, target_type: str, target_id: int) -> Optional[int]:
    from .models import Evidence, Finding, Loot
    if target_type == "service":
        return service_engagement(session, target_id)
    if target_type == "host":
        return host_engagement(session, target_id)
    if target_type == "finding":
        f = session.get(Finding, target_id)
        return f.engagement_id if f else None
    if target_type == "evidence":
        e = session.get(Evidence, target_id)
        return evidence_engagement(session, e) if e else None
    if target_type == "loot":
        lo = session.get(Loot, target_id)
        return lo.engagement_id if lo else None
    return None


def asset_engagement_ids(session: Session, asset_id: int) -> list[int]:
    from .models import Host
    from sqlmodel import select
    return sorted({h.engagement_id for h in
                   session.exec(select(Host).where(Host.asset_id == asset_id)).all()})
