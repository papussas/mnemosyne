# Mnemosyne

**Infra-first pentest knowledge base for humans _and_ AI agents.**

Document infrastructure (hosts → services → evidence) and derive **evidence-anchored
findings** from it, then ship them to Confluence + Jira. Built API-first so people and
AI agents (e.g. Claude Code via the included MCP server) write to one source of truth.

> Core principle: infra is the primary record; a finding is never free-floating — it is
> anchored to a service and cites proof (screenshots, tool output, banners).

---

## Features

- **Engagements → Hosts → Services → Findings**, with per-service **screenshots**, notes,
  and a visual **Services gallery**.
- **Assets** — every machine ever discovered (by IP/FQDN), tracked **across engagements**;
  from an asset you see its history, findings and which secrets work on it.
- **Findings** in a full report format (severity, CVSS, CVE, description, business impact,
  reproduction steps, remediation, references) with a `draft → confirmed → remediated →
  retested → …` lifecycle and a reusable **template library**.
- **Secrets** (credentials) as first-class objects with a "works-on" graph
  (*where does this hash work?*), **masked** in the UI with on-demand reveal.
- **Integrity** — a hash-chained, tamper-evident audit ledger over findings + evidence.
- **Activity inbox** — pull "what changed since I last looked" per engagement.
- **Coverage** metrics, **scan import** (nmap/masscan XML) + bulk create, idempotent
  host upsert (enrich, never duplicate).
- **Deliverables** — a verifiable export bundle (JSON + evidence + screenshots + integrity
  manifest) and a guided **Confluence + Jira** publish wizard (dry-run first).
- **Auth** — Argon2id passwords, JWT session cookie + optional TOTP 2FA for humans;
  scoped, revocable, hashed **API tokens** for agents. Roles: `admin`, `contributor`.
- **AI Agent Pack** — an MCP server + Claude Code skills so an agent can drive the whole
  thing (see [`agent-pack/`](agent-pack/README.md)).

## Stack

- **Backend:** Python 3.12, FastAPI, SQLModel, Postgres 16, Alembic. OpenAPI at `/docs`.
- **Frontend:** React + Vite + TypeScript + Tailwind (served by nginx, proxies `/api`).
- **Attachments:** content-addressed blob store (sha256) on a volume.

---

## Quick start (Docker — recommended)

Requirements: Docker + Docker Compose.

```bash
git clone <your-repo-url> mnemosyne && cd mnemosyne
cp .env.example .env
# EDIT .env: set a strong SECRET_KEY (openssl rand -hex 32), POSTGRES_PASSWORD,
# and the first-admin ADMIN_USERNAME / ADMIN_PASSWORD.
docker compose up -d --build
```

That starts three services:

| Service  | What it does                                                             | Default host port |
|----------|--------------------------------------------------------------------------|-------------------|
| `db`     | Postgres 16 (data in the `mneme_pgdata` volume)                          | `5433` → 5432     |
| `backend`| FastAPI; on boot waits for Postgres, runs `alembic upgrade head`, seeds the admin, serves the API | `8000`            |
| `frontend`| Vite build served by nginx; proxies `/api` → backend                    | `5173` → 80       |

Open **http://localhost:5173** and log in with the `ADMIN_USERNAME` / `ADMIN_PASSWORD`
you put in `.env`. API docs are at **http://localhost:8000/docs**.

The SPA calls `/api` on its own origin (nginx proxies it), so **no CORS setup is needed**
for the UI. Data persists in the `mneme_pgdata` (database) and `mneme_blobs` (screenshots)
volumes across rebuilds.

### Deploying on a shared host

Edit the published ports in `docker-compose.yml` to free ones (e.g. `8096:80` for the
frontend, `8097:8000` for the backend), and — if you want agents/tools to hit the API
directly — expose the backend port. Behind HTTPS, set `COOKIE_SECURE=true` and put the
UI origins in `CORS_ORIGINS`. To update a running stack: copy the new code and
`docker compose up -d --build` (the entrypoint re-runs migrations; the data volume is
preserved).

---

## Running without Docker (local dev)

Requirements: Python 3.11+, Node 20+, and a reachable Postgres.

```bash
# 1) Postgres (any instance) — e.g. a throwaway container just for the DB:
docker run -d --name mneme-pg -e POSTGRES_USER=mneme -e POSTGRES_PASSWORD=devpass \
  -e POSTGRES_DB=mnemosyne -p 5433:5432 postgres:16-alpine

# 2) .env at the repo root (config is read from real env vars, then ./.env or ../.env):
cp .env.example .env    # set POSTGRES_HOST=localhost, POSTGRES_PORT=5433,
                        # BLOB_DIR=./data/blobs, a SECRET_KEY, and admin creds

# 3) Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed_admin        # creates the first admin from .env
uvicorn app.main:app --reload       # API on http://localhost:8000  (docs at /docs)

# 4) Frontend (new shell)
cd frontend
npm install
npm run dev                         # UI on http://localhost:5173 (proxies /api → :8000)
```

---

## Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Database credentials |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `db` / `5432` in Docker; `localhost` / `5433` for local dev |
| `SECRET_KEY` | **Required.** JWT signing key — `openssl rand -hex 32`. The app refuses to boot on the built-in default unless `ALLOW_INSECURE_SECRET=true` (dev only). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Session lifetime (default 600 = 10h) |
| `BLOB_DIR` | Where attachments are stored (`/data/blobs` in Docker) |
| `MAX_UPLOAD_MB` | Attachment size cap (default 50) |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call the API (only needed if the UI isn't same-origin) |
| `COOKIE_SECURE` | `true` behind HTTPS |
| `ADMIN_EMAIL` / `ADMIN_USERNAME` / `ADMIN_PASSWORD` | First admin, seeded on boot |

## Users & roles

Log in as the seeded admin, then go to **Admin** to add users. Roles:
- **admin** — full control incl. user management and everyone's API tokens.
- **contributor** — read/write across the app.

Every user can create their own **API tokens** (Agents & Integrity page) for AI agents;
a token inherits the creator's role and can be scoped to a single engagement.

## Migrations

Alembic. After changing a model: `cd backend && alembic revision --autogenerate -m "msg"
&& alembic upgrade head`. In Docker the entrypoint runs `upgrade head` on every boot.

## AI Agent Pack

An MCP server + Claude Code skills that let an agent populate Mnemosyne during an
engagement (recon → services → evidence → findings → secrets → report). Setup and the
full tool list are in [`agent-pack/README.md`](agent-pack/README.md). The running app
also serves the pack as a download at `/agent_pack.zip`.

## Security notes

- Passwords hashed with Argon2id; API tokens stored only as sha256; TOTP 2FA optional.
- Agent API tokens **enforce their engagement scope**; human roles are global.
- Secrets are **masked** in API/UI (reveal on demand). They are **stored in plaintext at
  rest** — put the database on encrypted storage and restrict access; at-rest encryption
  is not yet implemented.
- Serve behind HTTPS in any real deployment (`COOKIE_SECURE=true`), and don't expose the
  Postgres port publicly.

## Project layout

```
backend/app/        FastAPI app: models, routers, security, authz, integrity, config
backend/alembic/    database migrations
frontend/src/       React SPA (pages, components, lib)
agent-pack/         MCP server (mnemosyne_mcp.py) + Claude Code skills + README
docker-compose.yml  db + backend + frontend
```
