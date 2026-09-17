from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..authz import assert_in_scope, scoped_list_engagement
from ..constants import WorksStatus
from ..db import get_session
from ..deps import Principal, current_reader, current_writer
from ..models import Credential, CredentialWorksOn, Host, Service
from ..schemas import CredentialCreate, CredentialUpdate
from .export import mask_secret

router = APIRouter(prefix="/credentials", tags=["credentials"])


def _pub(c: Credential) -> dict:
    """Serialize a credential with the secret masked (never cleartext by default)."""
    d = c.model_dump()
    d.pop("secret", None)
    d["secret_masked"] = mask_secret(c.secret)
    return d


def _guard(p: Principal, c: Credential) -> None:
    assert_in_scope(p, c.engagement_id)


@router.get("")
def list_creds(request: Request, session: Session = Depends(get_session),
               p: Principal = Depends(current_reader)):
    req = request.query_params.get("engagement_id")
    eng = scoped_list_engagement(p, int(req) if req else None)
    stmt = select(Credential)
    if eng is not None:
        stmt = stmt.where(Credential.engagement_id == eng)
    return [_pub(c) for c in session.exec(stmt.order_by(Credential.id.desc())).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_cred(body: CredentialCreate, session: Session = Depends(get_session),
                p: Principal = Depends(current_writer)):
    assert_in_scope(p, body.engagement_id)
    data = body.model_dump()
    data["cred_type"] = body.cred_type.value
    c = Credential(**data, author=p.actor)
    session.add(c); session.commit(); session.refresh(c)
    return _pub(c)


@router.get("/{cid}")
def get_cred(cid: int, session: Session = Depends(get_session),
             p: Principal = Depends(current_reader)):
    c = session.get(Credential, cid)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    _guard(p, c)
    return _pub(c)


@router.get("/{cid}/reveal")
def reveal_cred(cid: int, session: Session = Depends(get_session),
                p: Principal = Depends(current_reader)):
    """Return the cleartext secret. Kept out of the default read path so the UI can
    mask it and only fetch on demand."""
    c = session.get(Credential, cid)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    _guard(p, c)
    return {"id": c.id, "secret": c.secret}


@router.patch("/{cid}")
def update_cred(cid: int, body: CredentialUpdate, session: Session = Depends(get_session),
                p: Principal = Depends(current_writer)):
    c = session.get(Credential, cid)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    _guard(p, c)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v.value if hasattr(v, "value") else v)
    c.updated_at = datetime.utcnow()
    session.add(c); session.commit(); session.refresh(c)
    return _pub(c)


@router.delete("/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cred(cid: int, session: Session = Depends(get_session),
                p: Principal = Depends(current_writer)):
    c = session.get(Credential, cid)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    _guard(p, c)
    session.delete(c); session.commit()


class WorksOnBody(BaseModel):
    service_id: int
    status: WorksStatus = WorksStatus.untested
    note: str | None = None


def _link_context(session: Session, link: CredentialWorksOn) -> dict:
    svc = session.get(Service, link.service_id)
    host = session.get(Host, svc.host_id) if svc else None
    return {"link_id": link.id, "service_id": link.service_id, "status": link.status,
            "note": link.note, "tested_at": link.tested_at, "author": link.author,
            "service": f"{svc.port}/{svc.proto} {svc.service_type}" if svc else None,
            "host_ip": host.ip if host else None, "hostname": host.hostname if host else None}


@router.post("/{cid}/works-on", status_code=status.HTTP_201_CREATED)
def set_works_on(cid: int, body: WorksOnBody, session: Session = Depends(get_session),
                 p: Principal = Depends(current_writer)):
    c = session.get(Credential, cid)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    _guard(p, c)
    if not session.get(Service, body.service_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "service not found")
    link = CredentialWorksOn(credential_id=cid, service_id=body.service_id,
                             status=body.status.value, note=body.note,
                             tested_at=datetime.utcnow(), author=p.actor)
    session.add(link); session.commit(); session.refresh(link)
    return link


@router.get("/{cid}/works-on")
def list_works_on(cid: int, session: Session = Depends(get_session),
                  p: Principal = Depends(current_reader)):
    c = session.get(Credential, cid)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    _guard(p, c)
    links = session.exec(select(CredentialWorksOn)
                         .where(CredentialWorksOn.credential_id == cid)
                         .order_by(CredentialWorksOn.id.desc())).all()
    return [_link_context(session, link) for link in links]


@router.get("/{cid}/works-where")
def works_where(cid: int, session: Session = Depends(get_session),
                p: Principal = Depends(current_reader)):
    c = session.get(Credential, cid)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    _guard(p, c)
    links = session.exec(select(CredentialWorksOn).where(
        CredentialWorksOn.credential_id == cid, CredentialWorksOn.status == "works")).all()
    return [_link_context(session, link) for link in links]
