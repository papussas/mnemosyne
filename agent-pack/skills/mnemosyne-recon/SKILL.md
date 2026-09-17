---
name: mnemosyne-recon
description: Ingest recon results (nmap, service discovery) into Mnemosyne — create hosts and services under an engagement so the team and other agents can see coverage. Use when you have scan output to record.
---

# Recording recon into Mnemosyne

You have the `mnemosyne` MCP tools. Workflow:

1. `whoami()` to confirm your role, then `list_engagements()` and pick the engagement id you are working (ask the user if ambiguous).
2. Before scanning a host/subnet, `claim_target(engagement_id, target, ttl_minutes=120)` to avoid duplicate work. If it returns a 409 conflict, someone else owns it — move on.
3. `get_scope(engagement_id)` and only record in-scope targets.
4. For each live host, **upsert instead of blindly adding** so you never create duplicates: `upsert_host(engagement_id, ip, hostname, os, services=[{port, service_type, product, version}, ...])`. It creates the host if new, or enriches an existing one (fills only missing fields, adds only new services) and returns `{host, created, services_added}`. Use `find_host(engagement_id, ip)` first if you want to branch on existence. (Host creation is idempotent server-side too, so a stray `add_host` won't dup.)
5. Fastest path for a whole scan: skip per-host calls and use `import_scan(engagement_id, "/path/to/nmap.xml")` (or `bulk_add_hosts`) — both dedup hosts and services automatically.
6. Attach raw tool output as evidence on the service: `add_evidence(title="nmap -sV 10.0.0.5", content="<output>", service_id=...)`.
7. For a web service, capture a screenshot to a file and `attach_screenshot_file("service", service_id, "/path/to/portal.png")` — pass the PATH, not base64 (base64 args can blow the output-token limit).

Never invent data. Only record what the scan actually returned. Prefer one service per open port.
