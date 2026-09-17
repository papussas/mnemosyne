"""Bulk ingest: nmap/masscan XML import and structured JSON bulk host/service create.
Turns a scan into hosts+services in one request (dedup by ip / host+port+proto)."""
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..authz import assert_in_scope
from ..db import get_session
from ..deps import Principal, current_writer
from ..models import Engagement, Host, Service
from .hosts import _link_asset

router = APIRouter(tags=["ingest"])

_NMAP_MAP = {
    "http": "http", "http-proxy": "http", "http-alt": "http", "www": "http",
    "https": "https", "ssl/http": "https", "https-alt": "https",
    "ssh": "ssh", "microsoft-ds": "smb", "netbios-ssn": "smb", "smb": "smb",
    "ftp": "ftp", "ftps": "ftp", "ms-wbt-server": "rdp", "rdp": "rdp",
    "domain": "dns", "smtp": "smtp", "smtps": "smtp", "submission": "smtp",
    "mysql": "mysql", "ms-sql-s": "mssql", "ms-sql": "mssql",
    "postgresql": "postgres", "postgres": "postgres",
}


def _svc_type(name, tunnel, portid):
    n = (name or "").lower()
    if "http" in n and tunnel == "ssl":   # ssl-tunneled http => https (check before map)
        return "https"
    if n in _NMAP_MAP:
        return _NMAP_MAP[n]
    if "http" in n:
        return "http"
    if portid in (443, 8443):
        return "https"
    if portid in (80, 8080):
        return "http"
    return "other"


def _get_or_create_host(session, eng, ip, hostname, os_, actor):
    h = session.exec(select(Host).where(Host.engagement_id == eng.id, Host.ip == ip)).first()
    if h:
        if hostname and not h.hostname:
            h.hostname = hostname
        if os_ and not h.os:
            h.os = os_
        return h, False
    asset = _link_asset(session, eng.client_id, ip, hostname)
    h = Host(engagement_id=eng.id, asset_id=asset.id, ip=ip, hostname=hostname, os=os_, author=actor)
    session.add(h); session.flush()
    return h, True


def _add_service(session, host, port, proto, stype, product, version, banner, actor, desc=None):
    ex = session.exec(select(Service).where(
        Service.host_id == host.id, Service.port == port, Service.proto == proto)).first()
    if ex:
        return False
    session.add(Service(host_id=host.id, port=port, proto=proto, service_type=stype,
                        product=product, version=version, banner=banner,
                        description=desc, author=actor))
    return True


@router.post("/engagements/{eid}/import")
async def import_scan(eid: int, file: UploadFile = File(...),
                      session: Session = Depends(get_session),
                      p: Principal = Depends(current_writer)):
    """Import an nmap/masscan XML (-oX) file. Creates hosts + open-port services,
    de-duplicated against what's already in the engagement."""
    eng = session.get(Engagement, eid)
    if not eng:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "engagement not found")
    assert_in_scope(p, eid)
    content = await file.read()
    try:
        root = ET.fromstring(content)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "could not parse XML (expected nmap/masscan -oX output)")
    if root.tag != "nmaprun":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not an nmap/masscan XML (root <nmaprun> expected)")

    hc = he = sc = 0
    for host_el in root.findall("host"):
        ip = next((a.get("addr") for a in host_el.findall("address") if a.get("addrtype") == "ipv4"), None)
        if not ip:
            continue
        hn = host_el.find("hostnames/hostname")
        osm = host_el.find("os/osmatch")
        h, created = _get_or_create_host(session, eng, ip,
                                         hn.get("name") if hn is not None else None,
                                         osm.get("name") if osm is not None else None, p.actor)
        hc += 1 if created else 0
        he += 0 if created else 1
        for pe in host_el.findall("ports/port"):
            st = pe.find("state")
            if st is None or st.get("state") != "open":
                continue
            portid = int(pe.get("portid"))
            proto = pe.get("protocol", "tcp")
            se = pe.find("service")
            name = se.get("name") if se is not None else None
            product = se.get("product") if se is not None else None
            version = se.get("version") if se is not None else None
            tunnel = se.get("tunnel") if se is not None else None
            extra = se.get("extrainfo") if se is not None else None
            banner = " ".join(x for x in (product, version, extra) if x) or None
            if _add_service(session, h, portid, proto, _svc_type(name, tunnel, portid),
                            product, version, banner, p.actor):
                sc += 1
    session.commit()
    return {"hosts_created": hc, "hosts_existing": he, "services_created": sc}


class BulkService(BaseModel):
    port: int
    proto: str = "tcp"
    service_type: str = "other"
    product: str | None = None
    version: str | None = None
    description: str | None = None


class BulkHost(BaseModel):
    ip: str
    hostname: str | None = None
    os: str | None = None
    in_scope: bool = True
    notes: str | None = None
    services: list[BulkService] = []


class BulkBody(BaseModel):
    hosts: list[BulkHost]


class UpsertHost(BaseModel):
    ip: str
    hostname: str | None = None
    os: str | None = None
    notes: str | None = None
    tags: list[str] = []
    services: list[BulkService] = []


@router.post("/engagements/{eid}/hosts/upsert")
def upsert_host(eid: int, body: UpsertHost, session: Session = Depends(get_session),
                p: Principal = Depends(current_writer)):
    """Create the host if it doesn't exist in the engagement, otherwise ENRICH it
    (fill only missing hostname/os/notes, merge tags) and add only NEW services.
    Never duplicates. Returns the host, whether it was created, and services added."""
    eng = session.get(Engagement, eid)
    if not eng:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "engagement not found")
    assert_in_scope(p, eid)
    h, created = _get_or_create_host(session, eng, body.ip, body.hostname, body.os, p.actor)
    if not created:
        if body.notes and not h.notes:
            h.notes = body.notes
        if body.tags:
            h.tags = sorted(set((h.tags or []) + body.tags))
    added = 0
    for s in body.services:
        if _add_service(session, h, s.port, s.proto, s.service_type,
                        s.product, s.version, None, p.actor, s.description):
            added += 1
    session.commit(); session.refresh(h)
    return {"host": h.model_dump(), "created": created, "services_added": added}


@router.post("/engagements/{eid}/import/hosts")
def import_hosts(eid: int, body: BulkBody, session: Session = Depends(get_session),
                 p: Principal = Depends(current_writer)):
    """Bulk-create hosts (each with optional services) from a structured list.
    De-dupes by ip and host+port+proto. One call instead of many."""
    eng = session.get(Engagement, eid)
    if not eng:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "engagement not found")
    assert_in_scope(p, eid)
    hc = he = sc = 0
    for bh in body.hosts:
        h, created = _get_or_create_host(session, eng, bh.ip, bh.hostname, bh.os, p.actor)
        if created and (bh.notes or bh.in_scope is not True):
            h.notes = bh.notes; h.in_scope = bh.in_scope
        hc += 1 if created else 0
        he += 0 if created else 1
        for s in bh.services:
            if _add_service(session, h, s.port, s.proto, s.service_type,
                            s.product, s.version, None, p.actor, s.description):
                sc += 1
    session.commit()
    return {"hosts_created": hc, "hosts_existing": he, "services_created": sc}
