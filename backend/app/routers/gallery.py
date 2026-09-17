from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..db import get_session
from ..deps import Principal, current_reader
from ..authz import assert_in_scope
from ..models import Attachment, Host, Service

router = APIRouter(prefix="/gallery", tags=["gallery"])


@router.get("/services")
def services_gallery(engagement_id: int, q: Optional[str] = None, port: Optional[int] = None,
                     only_with_images: bool = False,
                     session: Session = Depends(get_session), p: Principal = Depends(current_reader)):
    """Services across an engagement (joined to their host) with attached screenshots,
    for quick visual triage. Filter by port and/or free text (description, notes,
    product, banner, type, hostname, ip)."""
    assert_in_scope(p, engagement_id)
    stmt = (select(Service, Host).join(Host, Host.id == Service.host_id)
            .where(Host.engagement_id == engagement_id))
    if port is not None:
        stmt = stmt.where(Service.port == port)
    rows = session.exec(stmt.order_by(Service.port)).all()

    needle = q.lower().strip() if q else None
    out = []
    for svc, host in rows:
        if needle:
            hay = " ".join(filter(None, [svc.description, svc.notes, svc.product, svc.version,
                                         svc.banner, svc.service_type, host.hostname, host.ip])).lower()
            if needle not in hay:
                continue
        atts = session.exec(select(Attachment).where(
            Attachment.target_type == "service", Attachment.target_id == svc.id)
            .order_by(Attachment.id.desc())).all()
        images = [{"id": a.id, "caption": a.caption, "has_thumb": bool(a.thumb_path)}
                  for a in atts if (a.mime or "").startswith("image/")]
        if only_with_images and not images:
            continue
        out.append({
            "service": svc.model_dump(),
            "host": {"id": host.id, "ip": host.ip, "hostname": host.hostname},
            "images": images,
            "attachment_count": len(atts),
        })
    return out
