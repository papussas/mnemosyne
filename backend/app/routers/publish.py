"""Direct publish to Confluence + Jira Cloud (the deterministic exporter).

dry_run=True (default) renders exactly what WOULD be created/updated and makes no
external calls — fully safe and testable. dry_run=False performs the live REST
calls using the supplied Cloud credentials and stores confluence_page_id /
jira_issue_key back on each finding so re-publishing UPDATES instead of duplicating.
"""
import ipaddress
import socket
from datetime import date, timedelta
from urllib.parse import urlparse
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import get_session
from ..authz import assert_in_scope
from ..deps import Principal, current_writer
from ..models import Engagement, Evidence, Finding
from .findings import _effective

router = APIRouter(tags=["publish"])

# severity -> remediation SLA (from Deliverables.md CVSS→SLA table) and Jira priority
SLA_DAYS = {"critical": 30, "high": 30, "medium": 90, "low": 180, "info": None}
JIRA_PRIORITY = {"critical": "Highest", "high": "High", "medium": "Medium",
                 "low": "Low", "info": "Lowest"}


# ---------- request models ----------
class ConfluenceCfg(BaseModel):
    base_url: str          # https://<site>.atlassian.net/wiki
    space_key: str
    parent_page_id: Optional[str] = None


class JiraCfg(BaseModel):
    base_url: str          # https://<site>.atlassian.net
    project_key: str
    issue_type: str = "Task"


class AuthCfg(BaseModel):
    email: str = ""
    api_token: str = ""


class PublishOptions(BaseModel):
    statuses: list[str] = ["draft", "open", "confirmed", "remediated", "risk_accepted"]
    create_confluence: bool = True
    create_jira: bool = True


class PublishRequest(BaseModel):
    confluence: Optional[ConfluenceCfg] = None
    jira: Optional[JiraCfg] = None
    auth: AuthCfg = AuthCfg()
    options: PublishOptions = PublishOptions()
    dry_run: bool = True


# ---------- rendering ----------
def render_confluence_xhtml(session: Session, f: Finding) -> str:
    d = _effective(session, f)
    rows = [
        ("Severity", (f.severity or "").upper()),
        ("CVSS", f.cvss_vector or "—"),
        ("CVE", f.cve or "—"),
        ("Affected asset", d.get("affected") or "—"),
        ("Status", f.status or "—"),
    ]
    table = "".join(f"<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>" for k, v in rows)
    ev = session.exec(select(Evidence).where(Evidence.finding_id == f.id)).all()
    ev_html = "".join(
        f"<li><strong>{escape(e.title)}</strong>"
        + (f"<br/><pre>{escape(e.content)}</pre>" if e.content else "") + "</li>" for e in ev)
    refs = "".join(f"<li>{escape(r)}</li>" for r in (f.references or []))

    def sec(title, body):
        return f"<h2>{escape(title)}</h2>{body}" if body else ""

    return (
        f"<table><tbody>{table}</tbody></table>"
        + sec("Description", f"<p>{escape(d.get('effective_description') or '')}</p>" if d.get("effective_description") else "")
        + sec("Business impact", f"<p>{escape(d.get('effective_business_impact') or '')}</p>" if d.get("effective_business_impact") else "")
        + sec("Reproduction steps", f"<pre>{escape(f.reproduction_steps)}</pre>" if f.reproduction_steps else "")
        + sec("Recommendation", f"<p>{escape(d.get('effective_remediation') or '')}</p>" if d.get("effective_remediation") else "")
        + sec("Evidence", f"<ul>{ev_html}</ul>" if ev_html else "")
        + sec("References", f"<ul>{refs}</ul>" if refs else "")
    )


def jira_fields(f: Finding, cfg: JiraCfg, title: str) -> dict:
    fields: dict = {
        "project": {"key": cfg.project_key},
        "issuetype": {"name": cfg.issue_type},
        "summary": f"[{(f.severity or '').upper()}] {title}",
        "priority": {"name": JIRA_PRIORITY.get(f.severity, "Medium")},
    }
    days = SLA_DAYS.get(f.severity)
    if days:
        fields["duedate"] = (date.today() + timedelta(days=days)).isoformat()
    return fields


# ---------- SSRF guard (Atlassian Cloud only) ----------
def _validate_atlassian(url: str) -> None:
    u = urlparse(url or "")
    if u.scheme != "https":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "base_url must be https")
    host = (u.hostname or "").lower()
    if not (host == "atlassian.net" or host.endswith(".atlassian.net")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "base_url host must be *.atlassian.net (Atlassian Cloud only)")
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"could not resolve host {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "base_url host resolves to a non-public address")


# ---------- endpoint ----------
@router.post("/engagements/{engagement_id}/publish")
def publish_engagement(engagement_id: int, req: PublishRequest,
                       session: Session = Depends(get_session),
                       p: Principal = Depends(current_writer)):
    eng = session.get(Engagement, engagement_id)
    if not eng:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "engagement not found")
    assert_in_scope(p, engagement_id)
    if req.confluence:
        _validate_atlassian(req.confluence.base_url)
    if req.jira:
        _validate_atlassian(req.jira.base_url)

    findings = session.exec(select(Finding).where(
        Finding.engagement_id == engagement_id,
        Finding.status.in_(req.options.statuses))).all()

    if not req.dry_run:
        if not (req.auth.email and req.auth.api_token):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "auth.email and auth.api_token required for a live publish")
        return _publish_live(session, eng, findings, req)

    # ----- dry run: build the plan, no external calls -----
    items = []
    for f in findings:
        d = _effective(session, f)
        title = d.get("effective_title") or f"Finding {f.id}"
        conf = None
        if req.options.create_confluence:
            conf = {"action": "update" if f.confluence_page_id else "create",
                    "page_id": f.confluence_page_id,
                    "title": f"[{(f.severity or '').upper()}] {title}",
                    "xhtml": render_confluence_xhtml(session, f)}
        jira = None
        if req.options.create_jira:
            jf = jira_fields(f, req.jira, title) if req.jira else {}
            jira = {"action": "update" if f.jira_issue_key else "create",
                    "key": f.jira_issue_key, "summary": jf.get("summary"),
                    "priority": (jf.get("priority") or {}).get("name"),
                    "duedate": jf.get("duedate")}
        items.append({"finding_id": f.id, "title": title, "severity": f.severity,
                      "confluence": conf, "jira": jira})

    return {"dry_run": True, "engagement": eng.name, "finding_count": len(findings),
            "space_key": req.confluence.space_key if req.confluence else None,
            "jira_project": req.jira.project_key if req.jira else None,
            "items": items}


def _publish_live(session: Session, eng: Engagement, findings: list[Finding],
                  req: PublishRequest) -> dict:
    import httpx  # local import: only needed for live path

    auth = (req.auth.email, req.auth.api_token)
    results, errors = [], []
    with httpx.Client(timeout=30, auth=auth,
                      headers={"Accept": "application/json"}) as client:
        for f in findings:
            d = _effective(session, f)
            title = d.get("effective_title") or f"Finding {f.id}"
            entry = {"finding_id": f.id, "title": title}
            # ---- Confluence ----
            if req.options.create_confluence and req.confluence:
                try:
                    page_title = f"[{(f.severity or '').upper()}] {title}"
                    body = {"storage": {"value": render_confluence_xhtml(session, f),
                                        "representation": "storage"}}
                    base = req.confluence.base_url.rstrip("/")
                    if f.confluence_page_id:
                        cur = client.get(f"{base}/rest/api/content/{f.confluence_page_id}?expand=version").json()
                        ver = cur.get("version", {}).get("number", 1) + 1
                        r = client.put(f"{base}/rest/api/content/{f.confluence_page_id}", json={
                            "id": f.confluence_page_id, "type": "page", "title": page_title,
                            "space": {"key": req.confluence.space_key},
                            "version": {"number": ver}, "body": body})
                    else:
                        payload = {"type": "page", "title": page_title,
                                   "space": {"key": req.confluence.space_key}, "body": body}
                        if req.confluence.parent_page_id:
                            payload["ancestors"] = [{"id": req.confluence.parent_page_id}]
                        r = client.post(f"{base}/rest/api/content", json=payload)
                    r.raise_for_status()
                    pid = str(r.json().get("id"))
                    f.confluence_page_id = pid
                    entry["confluence"] = {"page_id": pid,
                                           "url": f"{base}/pages/viewpage.action?pageId={pid}"}
                except Exception as e:  # noqa: BLE001
                    errors.append({"finding_id": f.id, "target": "confluence", "error": str(e)[:300]})
            # ---- Jira ----
            if req.options.create_jira and req.jira:
                try:
                    jbase = req.jira.base_url.rstrip("/")
                    fields = jira_fields(f, req.jira, title)
                    if f.jira_issue_key:
                        r = client.put(f"{jbase}/rest/api/3/issue/{f.jira_issue_key}",
                                       json={"fields": {k: fields[k] for k in ("summary", "priority", "duedate") if k in fields}})
                        r.raise_for_status()
                        entry["jira"] = {"key": f.jira_issue_key}
                    else:
                        r = client.post(f"{jbase}/rest/api/3/issue", json={"fields": fields})
                        r.raise_for_status()
                        key = r.json().get("key")
                        f.jira_issue_key = key
                        entry["jira"] = {"key": key, "url": f"{jbase}/browse/{key}"}
                except Exception as e:  # noqa: BLE001
                    errors.append({"finding_id": f.id, "target": "jira", "error": str(e)[:300]})
            session.add(f)
            results.append(entry)
        session.commit()
    return {"dry_run": False, "engagement": eng.name, "published": len(results),
            "results": results, "errors": errors}
