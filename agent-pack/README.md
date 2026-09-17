# Mnemosyne Agent Pack

Lets **Claude Code** pilot Mnemosyne (the infra-first pentest knowledge base) during an engagement.

## Contents
- `mnemosyne_mcp.py` — MCP server exposing Mnemosyne as tools (hosts, services, evidence, screenshots, findings, secrets, reuse graph, claims, export).
- `skills/` — Claude Code skills: `mnemosyne-recon`, `mnemosyne-finding`, `mnemosyne-report`.
- `mcp.json` — example MCP registration.
- `requirements.txt`.

## 1. Get an API token
In Mnemosyne → **Agents & Integrity → New token**. Copy the `mnem_…` value (shown once). The token acts as an agent under your account and inherits your role.

## 2. Install the MCP server
```bash
cd agent-pack
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# smoke test:
MNEME_URL="http://your-host:8096/api" MNEME_TOKEN="mnem_xxx" python mnemosyne_mcp.py   # ctrl-C to stop
```

## 3. Register with Claude Code
Either add it per-project via `.mcp.json` at your repo root (copy `mcp.json`, fix the absolute path + URL + token), or:
```bash
claude mcp add mnemosyne -- env MNEME_URL="http://your-host:8096/api" MNEME_TOKEN="mnem_xxx" python /abs/path/agent-pack/mnemosyne_mcp.py
```
Note the base URL ends in `/api` (the frontend nginx proxies `/api` → backend; or point directly at the backend host:port).

## 4. Install the skills
Copy the skill folders into your project so Claude Code loads them:
```bash
mkdir -p .claude/skills
cp -r agent-pack/skills/* .claude/skills/
```
Now ask Claude Code things like *"record this nmap output into engagement 3"* or *"log a finding for the SMB signing issue on host 10.0.0.5 with this screenshot"* and it will use the tools.

## Tool summary
whoami · list_engagements · get_scope · add_host · find_host · upsert_host · list_hosts · import_scan · bulk_add_hosts · add_service · list_services ·
add_evidence · attach_screenshot_file · attach_screenshot · add_credential · cred_works_on · where_cred_works ·
create_finding · update_finding · update_object · query_findings · list_credentials · mark_credential_validated · list_assets · asset_history · inbox · claim_target · export_engagement · list_attachments · move_attachment · delete_attachment

## Notes & troubleshooting
- **`mcp` version**: this pack targets the FastMCP 1.x API. `requirements.txt` pins `mcp>=1.2.0,<2` — mcp 2.x renamed `FastMCP` and breaks the import. If you see `ImportError: cannot import name 'FastMCP'`, you have 2.x; reinstall with the pin.
- **Reloading**: Claude Code loads MCP servers at startup — after editing `.mcp.json`, env, or the server code you must **restart Claude Code** for changes to take effect.
- **Screenshots**: prefer **`attach_screenshot_file(target_type, target_id, "/path/to/img.png")`** — it passes a file *path*, so the MCP server reads/encodes the bytes and the model never emits base64 (base64 arguments can exceed the output-token cap and error out). `attach_screenshot` (raw/line-wrapped base64 or a `data:` URI) still exists for tiny inline images; either way the **server sniffs the real image type from the bytes**, so `mime` is best-effort.
- **Large result sets**: `query_findings` defaults to `summary=True, limit=100` so responses stay small on big engagements. Pass `summary=False` for full detail and `limit`/`offset` to page.
