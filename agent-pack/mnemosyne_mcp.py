#!/usr/bin/env python3
"""Mnemosyne MCP server — lets Claude Code drive the Mnemosyne pentest KB.

Config via env:
  MNEME_URL    Base API URL, e.g. http://your-host:8096/api  (note the /api)
  MNEME_TOKEN  An API token (mnem_...) minted in the UI under "Agents & Integrity"

Run:  MNEME_URL=... MNEME_TOKEN=... python mnemosyne_mcp.py
"""
import base64
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("MNEME_URL", "http://localhost:5173/api").rstrip("/")
TOKEN = os.environ.get("MNEME_TOKEN", "")
mcp = FastMCP("mnemosyne")


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE, headers={"X-API-Key": TOKEN}, timeout=30)


def _req(method: str, path: str, **kw):
    with _client() as c:
        r = c.request(method, path, **kw)
        r.raise_for_status()
        if r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return r.content


@mcp.tool()
def whoami() -> dict:
    """Return the identity/role this token authenticates as."""
    return _req("GET", "/auth/me")


@mcp.tool()
def list_engagements() -> list:
    """List engagements (id, name, client, status)."""
    return _req("GET", "/engagements")


@mcp.tool()
def get_scope(engagement_id: int) -> list:
    """Get the in/out scope rules for an engagement."""
    return _req("GET", "/scope", params={"engagement_id": engagement_id})


@mcp.tool()
def add_host(engagement_id: int, ip: str, hostname: str = "", os: str = "", notes: str = "") -> dict:
    """Add a host to an engagement (auto-links to the client Asset)."""
    return _req("POST", "/hosts", json={"engagement_id": engagement_id, "ip": ip,
                "hostname": hostname or None, "os": os or None, "notes": notes or None})


@mcp.tool()
def find_host(engagement_id: int, ip: str) -> dict:
    """Return the existing host with this IP in the engagement, or {} if none. Use
    before creating to decide whether to add or enrich."""
    rows = _req("GET", "/hosts", params={"engagement_id": engagement_id, "ip": ip})
    return rows[0] if rows else {}


@mcp.tool()
def upsert_host(engagement_id: int, ip: str, hostname: str = "", os: str = "",
                notes: str = "", services: list = None) -> dict:
    """Create the host if it's new, else ENRICH it: fills only missing hostname/os/notes,
    merges tags, and adds only NEW services (dedup by port+proto). Never duplicates.
    `services` = list of {port, proto?, service_type?, product?, version?}. Returns
    {host, created, services_added}. Prefer this over add_host/add_service for recon."""
    body = {"ip": ip}
    if hostname:
        body["hostname"] = hostname
    if os:
        body["os"] = os
    if notes:
        body["notes"] = notes
    if services:
        body["services"] = services
    return _req("POST", f"/engagements/{engagement_id}/hosts/upsert", json=body)


@mcp.tool()
def list_hosts(engagement_id: int) -> list:
    """List hosts in an engagement."""
    return _req("GET", "/hosts", params={"engagement_id": engagement_id})


@mcp.tool()
def add_service(host_id: int, port: int, service_type: str = "other", product: str = "",
                version: str = "", description: str = "") -> dict:
    """Record a service on a host. service_type: http/https/ssh/smb/ftp/rdp/dns/smtp/mysql/mssql/postgres/other."""
    return _req("POST", "/services", json={"host_id": host_id, "port": port,
                "service_type": service_type, "product": product or None,
                "version": version or None, "description": description or None})


@mcp.tool()
def list_services(host_id: int) -> list:
    """List services on a host."""
    return _req("GET", "/services", params={"host_id": host_id})


@mcp.tool()
def add_evidence(title: str, content: str = "", finding_id: Optional[int] = None,
                 service_id: Optional[int] = None, host_id: Optional[int] = None) -> dict:
    """Record an authored evidence entry (tool output / observation), linked to a finding, service, or host."""
    return _req("POST", "/evidence", json={"title": title, "content": content or None,
                "finding_id": finding_id, "service_id": service_id, "host_id": host_id})


@mcp.tool()
def attach_screenshot(target_type: str, target_id: int, filename: str, image_base64: str,
                      mime: str = "image/png", caption: str = "") -> dict:
    """Attach a screenshot/image (base64) to a service|finding|evidence|loot|host.

    PREFER `attach_screenshot_file` for anything but tiny images — passing base64
    here forces the model to emit the whole blob and can blow the output-token cap.
    The server sniffs the real image type from the bytes, so `mime` is best-effort.
    A data: URI prefix or line-wrapped base64 is handled automatically."""
    b64 = (image_base64 or "").strip()
    if b64.startswith("data:") and "," in b64:
        b64 = b64.split(",", 1)[1]
    b64 = "".join(b64.split())
    return _req("POST", "/attachments/base64", json={"target_type": target_type,
                "target_id": target_id, "filename": filename, "mime": mime,
                "data_b64": b64, "caption": caption or None})


@mcp.tool()
def attach_screenshot_file(target_type: str, target_id: int, path: str,
                           mime: str = "", caption: str = "") -> dict:
    """Attach a LOCAL file (screenshot/image/pcap/pdf) to a service|finding|evidence|
    loot|host by its filesystem PATH. The MCP server (this local process) reads and
    base64-encodes the file itself, so the model never emits the bytes -- use this for
    screenshots to stay under the output-token limit. filename/mime are inferred from
    the path (the backend also sniffs the real type from the bytes); mime can be overridden."""
    import base64 as _b64
    import pathlib
    p = pathlib.Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"not a file: {p}")
    content = p.read_bytes()
    if not content:
        raise ValueError(f"file is empty: {p}")
    guessed = mime or {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp",
    }.get(p.suffix.lower(), "application/octet-stream")
    return _req("POST", "/attachments/base64", json={"target_type": target_type,
                "target_id": target_id, "filename": p.name, "mime": guessed,
                "data_b64": _b64.b64encode(content).decode(), "caption": caption or None})


@mcp.tool()
def list_attachments(target_type: str, target_id: int) -> list:
    """List attachments on a service|finding|evidence|loot|host (id, filename, mime, caption)."""
    return _req("GET", "/attachments", params={"target_type": target_type, "target_id": target_id})


@mcp.tool()
def delete_attachment(attachment_id: int) -> dict:
    """Delete an attachment by id. The shared image blob is kept as long as another
    attachment still references it (safe for removing duplicate copies)."""
    _req("DELETE", f"/attachments/{attachment_id}")
    return {"deleted": attachment_id}


@mcp.tool()
def move_attachment(attachment_id: int, target_type: str, target_id: int, caption: str = "") -> dict:
    """Move (re-target) an attachment to a different owner -- e.g. from a finding to a
    service. Optionally update the caption."""
    body = {"target_type": target_type, "target_id": target_id}
    if caption:
        body["caption"] = caption
    return _req("PATCH", f"/attachments/{attachment_id}", json=body)


@mcp.tool()
def add_credential(engagement_id: int, cred_type: str = "password", username: str = "",
                   secret: str = "", realm: str = "", source: str = "") -> dict:
    """Store a found secret. cred_type: password/ntlm_hash/kerberos/ssh_key/token/other."""
    return _req("POST", "/credentials", json={"engagement_id": engagement_id, "cred_type": cred_type,
                "username": username or None, "secret": secret or None,
                "realm": realm or None, "source": source or None})


@mcp.tool()
def cred_works_on(credential_id: int, service_id: int, status: str = "works", note: str = "") -> dict:
    """Record whether a credential works/failed/untested against a service (the reuse graph)."""
    return _req("POST", f"/credentials/{credential_id}/works-on",
                json={"service_id": service_id, "status": status, "note": note or None})


@mcp.tool()
def where_cred_works(credential_id: int) -> list:
    """List every service a credential is confirmed to work on."""
    return _req("GET", f"/credentials/{credential_id}/works-where")


_UPDATABLE = {
    "client": "/clients", "engagement": "/engagements", "scope": "/scope",
    "host": "/hosts", "service": "/services", "evidence": "/evidence",
    "credential": "/credentials", "loot": "/loot", "finding": "/findings",
    "finding-template": "/finding-templates", "asset": "/assets",
}


@mcp.tool()
def update_object(kind: str, object_id: int, fields: dict) -> dict:
    """Update (PATCH) ANY object by kind + id with a dict of fields — only the fields
    you pass change. kind is one of: client, engagement, scope, host, service,
    evidence, credential, loot, finding, finding-template, asset.
    Example: update_object("credential", 12, {"validated": true})."""
    path = _UPDATABLE.get(kind)
    if not path:
        return {"error": f"unknown kind '{kind}'; use one of {sorted(_UPDATABLE)}"}
    return _req("PATCH", f"{path}/{object_id}", json=fields)


@mcp.tool()
def list_credentials(engagement_id: int) -> list:
    """List credentials/secrets in an engagement (secret value is masked)."""
    return _req("GET", "/credentials", params={"engagement_id": engagement_id})


@mcp.tool()
def mark_credential_validated(credential_id: int, validated: bool = True) -> dict:
    """Mark a credential validated (or not). Convenience for update_object on a credential."""
    return _req("PATCH", f"/credentials/{credential_id}", json={"validated": validated})


@mcp.tool()
def create_finding(engagement_id: int, service_id: int, title: str = "", severity: str = "medium",
                   description: str = "", business_impact: str = "", reproduction_steps: str = "",
                   remediation: str = "", cve: str = "", cvss_vector: str = "",
                   status: str = "draft", template_id: int = 0) -> dict:
    """Create a finding anchored to a service. severity: info/low/medium/high/critical.
    status: draft/open/confirmed/remediated/retested/risk_accepted/false_positive."""
    return _req("POST", "/findings", json={"engagement_id": engagement_id, "service_id": service_id,
                "title": title, "severity": severity, "description": description or None,
                "business_impact": business_impact or None, "reproduction_steps": reproduction_steps or None,
                "remediation": remediation or None, "cve": cve or None,
                "cvss_vector": cvss_vector or None, "status": status,
                "title": title or None, "template_id": template_id or None})


@mcp.tool()
def update_finding(finding_id: int, **fields) -> dict:
    """Update a finding (e.g. status='confirmed', severity, description, remediation…)."""
    return _req("PATCH", f"/findings/{finding_id}", json=fields)


@mcp.tool()
def query_findings(engagement_id: int, status: str = "", summary: bool = True,
                   limit: int = 100, offset: int = 0) -> list:
    """List findings in an engagement. summary=True (default) returns a compact
    projection (id/title/severity/status/cve/service_id) that stays small even on
    large engagements; set summary=False for full detail. Use limit/offset to page."""
    params = {"engagement_id": engagement_id, "summary": summary, "limit": limit, "offset": offset}
    if status:
        params["status"] = status
    return _req("GET", "/findings", params=params)


@mcp.tool()
def list_assets(engagement_id: Optional[int] = None, q: str = "") -> list:
    """List assets (all discovered machines), optionally scoped to an engagement or text query."""
    params = {}
    if engagement_id:
        params["engagement_id"] = engagement_id
    if q:
        params["q"] = q
    return _req("GET", "/assets", params=params)


@mcp.tool()
def asset_history(asset_id: int) -> dict:
    """Cross-engagement history for an asset: prior services + findings."""
    return _req("GET", f"/assets/{asset_id}/history")


@mcp.tool()
def inbox(engagement_id: int, since: str = "", limit: int = 100, exclude_self: bool = True) -> dict:
    """Pull the engagement ACTIVITY FEED -- what changed since you last looked: new
    hosts/services/findings/secrets, cred-test results, evidence and screenshots
    added by other users/agents. Poll again passing the returned `cursor` as `since`
    (repeat while has_more is true). exclude_self hides your own actions so you only
    see others' updates worth continuing from."""
    params = {"limit": limit}
    if since:
        params["since"] = since
    if exclude_self:
        try:
            params["exclude_actor"] = _req("GET", "/auth/me").get("actor", "")
        except Exception:
            pass
    return _req("GET", f"/engagements/{engagement_id}/activity", params=params)


@mcp.tool()
def claim_target(engagement_id: int, target: str, ttl_minutes: int = 120) -> dict:
    """Claim a host/subnet for TTL minutes to avoid duplicate work with teammates/agents."""
    return _req("POST", "/claims", json={"engagement_id": engagement_id, "target": target,
                "ttl_minutes": ttl_minutes})


@mcp.tool()
def export_engagement(engagement_id: int, out_path: str, statuses: str = "confirmed") -> str:
    """Download the engagement export bundle (zip) to out_path. Default: confirmed findings only."""
    data = _req("GET", f"/engagements/{engagement_id}/export", params={"statuses": statuses})
    with open(out_path, "wb") as fh:
        fh.write(data)
    return f"wrote {len(data)} bytes to {out_path}"


@mcp.tool()
def import_scan(engagement_id: int, path: str) -> dict:
    """Import an nmap/masscan XML (-oX) file from a LOCAL path -- bulk-creates hosts +
    open-port services in one call (de-duped). Far faster than add_host/add_service loops."""
    import os as _os
    with open(path, "rb") as fh:
        data = fh.read()
    with _client() as cl:
        r = cl.post(f"/engagements/{engagement_id}/import",
                    files={"file": (_os.path.basename(path) or "scan.xml", data, "text/xml")})
        r.raise_for_status()
        return r.json()


@mcp.tool()
def bulk_add_hosts(engagement_id: int, hosts: list) -> dict:
    """Bulk-create hosts (each optionally with services) in ONE call. `hosts` is a list of
    {ip, hostname?, os?, notes?, services:[{port, proto?, service_type?, product?, version?}]}."""
    return _req("POST", f"/engagements/{engagement_id}/import/hosts", json={"hosts": hosts})


@mcp.tool()
def get_coverage(engagement_id: int) -> dict:
    """Engagement progress: hosts (total/in-scope/with-services), services (with/without
    findings), findings by severity & status, secrets validated, scope-rule count."""
    return _req("GET", f"/engagements/{engagement_id}/coverage")


@mcp.tool()
def list_finding_templates() -> list:
    """List reusable finding templates (title, category, default severity, remediation)."""
    return _req("GET", "/finding-templates")


@mcp.tool()
def create_finding_template(title: str, description: str = "", business_impact: str = "",
                            remediation: str = "", default_severity: str = "medium",
                            category: str = "", client_id: int = 0) -> dict:
    """Create a reusable finding template; instances can inherit its narrative via
    create_finding(..., template_id=<id>)."""
    return _req("POST", "/finding-templates", json={
        "title": title, "description": description or None, "business_impact": business_impact or None,
        "remediation": remediation or None, "default_severity": default_severity,
        "category": category or None, "client_id": client_id or None})


if __name__ == "__main__":
    mcp.run()
