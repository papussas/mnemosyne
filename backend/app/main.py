from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .authz import host_engagement
from .crud import make_crud_router
from .models import (Client, Engagement, FindingTemplate, Loot, Scope, Service)
from .routers import (assets, attachments, auth, claims, credentials, evidence,
                      activity, coverage, export, findings, gallery, hosts, ingest, integrity, meta, publish, tokens)
from .schemas import (ClientCreate, ClientUpdate, EngagementCreate,
                      EngagementUpdate, FindingTemplateCreate,
                      FindingTemplateUpdate, LootCreate, LootUpdate, ScopeCreate,
                      ScopeUpdate, ServiceCreate, ServiceUpdate)

app = FastAPI(title="Mnemosyne API", version="0.1.0",
              description="Infra-first pentest knowledge base for humans and AI agents.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Refuse to run with the built-in insecure SECRET_KEY unless explicitly allowed (dev).
if settings.secret_key in ("", "dev-insecure-change-me") and not settings.allow_insecure_secret:
    raise RuntimeError(
        "SECRET_KEY is unset or the insecure default. Set a strong SECRET_KEY "
        "(openssl rand -hex 32), or ALLOW_INSECURE_SECRET=true for local dev only."
    )


@app.middleware("http")
async def _security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp



@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "mnemosyne"}


# custom routers
for r in (auth.router, tokens.router, hosts.router, assets.router, evidence.router,
          findings.router, credentials.router, attachments.router, claims.router,
          integrity.router, meta.router, gallery.router, export.router, publish.router, activity.router, ingest.router, coverage.router):
    app.include_router(r)

# generic CRUD routers
app.include_router(make_crud_router(
    model=Client, create_schema=ClientCreate, update_schema=ClientUpdate,
    prefix="clients", tag="clients"))
app.include_router(make_crud_router(
    model=Engagement, create_schema=EngagementCreate, update_schema=EngagementUpdate,
    prefix="engagements", tag="engagements", filter_fields=["client_id"],
    eng_of_obj=lambda s, o: o.id, eng_of_payload=lambda s, d: -1))  # scoped agents can't create engagements
app.include_router(make_crud_router(
    model=Scope, create_schema=ScopeCreate, update_schema=ScopeUpdate,
    prefix="scope", tag="scope", filter_fields=["engagement_id"],
    eng_of_obj=lambda s, o: o.engagement_id, eng_of_payload=lambda s, d: d.get("engagement_id")))
app.include_router(make_crud_router(
    model=Service, create_schema=ServiceCreate, update_schema=ServiceUpdate,
    prefix="services", tag="services", filter_fields=["host_id"], set_author=True,
    eng_of_obj=lambda s, o: host_engagement(s, o.host_id),
    eng_of_payload=lambda s, d: host_engagement(s, d.get("host_id"))))
app.include_router(make_crud_router(
    model=Loot, create_schema=LootCreate, update_schema=LootUpdate,
    prefix="loot", tag="loot", filter_fields=["engagement_id", "host_id", "service_id"],
    set_author=True,
    eng_of_obj=lambda s, o: o.engagement_id, eng_of_payload=lambda s, d: d.get("engagement_id")))
app.include_router(make_crud_router(
    model=FindingTemplate, create_schema=FindingTemplateCreate,
    update_schema=FindingTemplateUpdate, prefix="finding-templates", tag="finding-templates",
    filter_fields=["client_id"]))
