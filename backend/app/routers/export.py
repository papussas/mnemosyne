"""Engagement export bundle: a self-describing, integrity-verifiable zip that is
the canonical hand-off artifact (feeds Rovo, the direct Confluence/Jira exporter,
a human, or any consumer)."""
import io
import json
import os
import zipfile
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..deps import Principal, current_reader
from ..authz import assert_in_scope
from ..integrity import verify_chain
from ..models import (Attachment, Client, Credential, CredentialWorksOn,
                      Engagement, Evidence, Finding, Host, Scope, Service)
from .findings import _effective

router = APIRouter(tags=["export"])

_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
        "image/gif": ".gif", "image/webp": ".webp"}


def mask_secret(s: str | None) -> str | None:
    """Obfuscate a secret for export: 'pass123' -> 'pa***23'. Never emit cleartext."""
    if not s:
        return None
    s = str(s)
    n = len(s)
    if n <= 4:
        return "*" * n  # too short to reveal any chars safely
    stars = min(n - 4, 6)
    return f"{s[:2]}{'*' * stars}{s[-2:]}"


def _blob_bytes(sha: str) -> bytes | None:
    path = os.path.join(settings.blob_dir, sha[:2], sha[2:4], sha)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()


@router.get("/engagements/{engagement_id}/export")
def export_engagement(engagement_id: int, statuses: str = "confirmed",
                      session: Session = Depends(get_session),
                      p: Principal = Depends(current_reader)):
    """Export bundle. By default only CONFIRMED findings and their artifacts are
    included (the deliverable set); pass ?statuses=confirmed,retested to widen."""
    assert_in_scope(p, engagement_id)
    eng = session.get(Engagement, engagement_id)
    if not eng:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "engagement not found")
    client = session.get(Client, eng.client_id)
    status_list = [s.strip() for s in statuses.split(",") if s.strip()]

    hosts = session.exec(select(Host).where(Host.engagement_id == engagement_id)).all()
    host_ids = [h.id for h in hosts]
    services = session.exec(select(Service).where(Service.host_id.in_(host_ids))).all() if host_ids else []
    findings = session.exec(select(Finding).where(
        Finding.engagement_id == engagement_id, Finding.status.in_(status_list))).all()
    finding_ids = [f.id for f in findings]
    confirmed_svc_ids = {f.service_id for f in findings}  # only services anchoring an included finding
    creds = session.exec(select(Credential).where(Credential.engagement_id == engagement_id)).all()
    scope = session.exec(select(Scope).where(Scope.engagement_id == engagement_id)).all()

    # evidence only for the included findings (and the services they anchor)
    evidence = session.exec(select(Evidence)).all()
    evidence = [e for e in evidence if (e.finding_id in finding_ids) or
                (e.service_id in confirmed_svc_ids)]

    # ---- findings.json (Deliverables finding format + context) ----
    findings_out = []
    integrity_out = {"findings": []}
    for f in findings:
        d = _effective(session, f)
        img_refs = []
        atts = session.exec(select(Attachment).where(
            Attachment.target_type == "finding", Attachment.target_id == f.id)).all()
        for a in atts:
            if (a.mime or "").startswith("image/"):
                img_refs.append(f"images/findings/{f.id}/{a.sha256}{_EXT.get(a.mime, '.bin')}")
        ev_ids = [e.id for e in evidence if e.finding_id == f.id]
        findings_out.append({
            "id": f.id, "title": d.get("effective_title"), "severity": f.severity,
            "status": f.status, "cvss_vector": f.cvss_vector, "cve": f.cve,
            "affected": d.get("affected"), "host": d.get("host"), "asset": d.get("asset"),
            "service_id": f.service_id,
            "description": d.get("effective_description"),
            "business_impact": d.get("effective_business_impact"),
            "reproduction_steps": f.reproduction_steps,
            "remediation": d.get("effective_remediation"),
            "references": f.references, "raw_notes": f.raw_notes,
            "evidence_ids": ev_ids, "images": img_refs,
            "author": f.author, "created_at": f.created_at.isoformat(),
        })
        integrity_out["findings"].append({"id": f.id, "content_hash": f.content_hash})

    # ---- credentials.json (with works-on summary) ----
    creds_out = []
    for c in creds:
        links = session.exec(select(CredentialWorksOn).where(CredentialWorksOn.credential_id == c.id)).all()
        works = []
        for l in links:
            s = session.get(Service, l.service_id)
            h = session.get(Host, s.host_id) if s else None
            works.append({"status": l.status, "service": f"{s.port}/{s.proto}" if s else None,
                          "host_ip": h.ip if h else None})
        creds_out.append({"id": c.id, "cred_type": c.cred_type, "username": c.username,
                          "secret_obfuscated": mask_secret(c.secret), "realm": c.realm,
                          "source": c.source, "validated": c.validated, "works_on": works})

    sev_counts = Counter(f.severity for f in findings)
    manifest = {
        "tool": "mnemosyne", "export_version": 1,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "engagement": {"id": eng.id, "name": eng.name, "status": eng.status,
                       "client": client.name if client else None,
                       "start_date": eng.start_date.isoformat() if eng.start_date else None,
                       "end_date": eng.end_date.isoformat() if eng.end_date else None},
        "scope": [{"rule_type": s.rule_type, "pattern": s.pattern, "note": s.note} for s in scope],
        "findings_included": status_list,
        "counts": {"hosts": len(hosts), "services": len(services),
                   "findings": len(findings), "credentials": len(creds),
                   "findings_by_severity": dict(sev_counts)},
        "integrity": verify_chain(session),
    }
    evidence_out = [{"id": e.id, "title": e.title, "content": e.content, "source": e.source,
                     "finding_id": e.finding_id, "service_id": e.service_id, "host_id": e.host_id,
                     "author": e.author, "content_hash": e.content_hash,
                     "created_at": e.created_at.isoformat()} for e in evidence]

    # ---- build the zip ----
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("findings.json", json.dumps(findings_out, indent=2))
        z.writestr("evidence.json", json.dumps(evidence_out, indent=2))
        z.writestr("credentials.json", json.dumps(creds_out, indent=2))
        z.writestr("integrity.json", json.dumps(integrity_out, indent=2))
        # finding images
        for f in findings:
            for a in session.exec(select(Attachment).where(
                    Attachment.target_type == "finding", Attachment.target_id == f.id)).all():
                if not (a.mime or "").startswith("image/"):
                    continue
                data = _blob_bytes(a.sha256)
                if data:
                    z.writestr(f"images/findings/{f.id}/{a.sha256}{_EXT.get(a.mime, '.bin')}", data)
        # service screenshots — only services that anchor an included finding
        for s in services:
            if s.id not in confirmed_svc_ids:
                continue
            for a in session.exec(select(Attachment).where(
                    Attachment.target_type == "service", Attachment.target_id == s.id)).all():
                if not (a.mime or "").startswith("image/"):
                    continue
                data = _blob_bytes(a.sha256)
                if data:
                    z.writestr(f"images/services/{s.id}/{a.sha256}{_EXT.get(a.mime, '.bin')}", data)
    buf.seek(0)

    import re
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", (eng.name or "engagement"))[:80]
    fname = f"mnemosyne_{safe}_{engagement_id}.zip"
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})
