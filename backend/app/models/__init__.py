"""Mnemosyne data model. Enum-valued columns are stored as plain strings
(validated at the schema layer) to keep migrations simple while the findings
taxonomy in Plan.md §4 is still being finalized."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Text, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.utcnow()


# ---------------- identity ----------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    username: str = Field(index=True, unique=True)
    full_name: Optional[str] = None
    hashed_password: str
    role: str = Field(default="contributor")
    is_active: bool = True
    totp_secret: Optional[str] = None
    totp_enabled: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ApiToken(SQLModel, table=True):
    """Agent credential. Only the sha256 hash is stored; the raw token is shown once."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    prefix: str = Field(index=True)
    token_hash: str = Field(index=True, unique=True)
    role: str = Field(default="contributor")
    engagement_id: Optional[int] = Field(default=None, foreign_key="engagement.id")
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    expires_at: Optional[datetime] = None
    revoked: bool = False
    last_used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_now)


# ---------------- tenancy / scope ----------------
class Client(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Engagement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    status: str = Field(default="active")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Scope(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    engagement_id: int = Field(foreign_key="engagement.id", index=True)
    rule_type: str = Field(default="include")  # include | exclude
    pattern: str  # CIDR or domain glob
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


# ---------------- assets (cross-engagement memory) ----------------
class Asset(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("client_id", "ip", "fqdn", name="uq_asset_identity"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    ip: Optional[str] = Field(default=None, index=True)
    fqdn: Optional[str] = Field(default=None, index=True)
    label: Optional[str] = None
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    first_seen: datetime = Field(default_factory=_now)
    last_seen: datetime = Field(default_factory=_now)
    created_at: datetime = Field(default_factory=_now)


# ---------------- infra ----------------
class Host(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    engagement_id: int = Field(foreign_key="engagement.id", index=True)
    asset_id: Optional[int] = Field(default=None, foreign_key="asset.id", index=True)
    ip: str = Field(index=True)
    hostname: Optional[str] = Field(default=None, index=True)
    os: Optional[str] = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    in_scope: bool = True
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Service(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    host_id: int = Field(foreign_key="host.id", index=True)
    port: int
    proto: str = Field(default="tcp")
    service_type: str = Field(default="other")
    product: Optional[str] = None
    version: Optional[str] = None
    banner: Optional[str] = Field(default=None, sa_column=Column(Text))
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ---------------- evidence & attachments ----------------
class Evidence(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    host_id: Optional[int] = Field(default=None, foreign_key="host.id", index=True)
    service_id: Optional[int] = Field(default=None, foreign_key="service.id", index=True)
    finding_id: Optional[int] = Field(default=None, foreign_key="finding.id", index=True)
    title: str
    content: Optional[str] = Field(default=None, sa_column=Column(Text))
    source: Optional[str] = None
    content_hash: Optional[str] = Field(default=None, index=True)  # integrity
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Attachment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    target_type: str = Field(index=True)  # service|finding|evidence|loot|host
    target_id: int = Field(index=True)
    filename: str
    mime: str
    sha256: str = Field(index=True)  # content-addressed => inherent integrity
    size: int = 0
    caption: Optional[str] = None
    source: Optional[str] = None  # manual | claude-code | burp | ...
    thumb_path: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


# ---------------- credentials & loot ----------------
class Credential(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    engagement_id: int = Field(foreign_key="engagement.id", index=True)
    cred_type: str = Field(default="password")
    username: Optional[str] = Field(default=None, index=True)
    secret: Optional[str] = Field(default=None, sa_column=Column(Text))
    realm: Optional[str] = None
    source: Optional[str] = None
    validated: bool = False
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class CredentialWorksOn(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    credential_id: int = Field(foreign_key="credential.id", index=True)
    service_id: int = Field(foreign_key="service.id", index=True)
    status: str = Field(default="untested")  # works|failed|untested
    note: Optional[str] = None
    tested_at: Optional[datetime] = None
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class Loot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    engagement_id: int = Field(foreign_key="engagement.id", index=True)
    host_id: Optional[int] = Field(default=None, foreign_key="host.id", index=True)
    service_id: Optional[int] = Field(default=None, foreign_key="service.id", index=True)
    loot_type: str = Field(default="other")
    title: str
    content: Optional[str] = Field(default=None, sa_column=Column(Text))
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


# ---------------- findings ----------------
class FindingTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="client.id", index=True)
    title: str = Field(index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    business_impact: Optional[str] = Field(default=None, sa_column=Column(Text))
    remediation: Optional[str] = Field(default=None, sa_column=Column(Text))
    references: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    default_severity: str = Field(default="medium")
    category: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Finding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    engagement_id: int = Field(foreign_key="engagement.id", index=True)
    service_id: int = Field(foreign_key="service.id", index=True)  # required anchor
    asset_id: Optional[int] = Field(default=None, foreign_key="asset.id", index=True)  # cross-engagement link
    template_id: Optional[int] = Field(default=None, foreign_key="findingtemplate.id", index=True)
    title: Optional[str] = None  # may inherit from template
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    business_impact: Optional[str] = Field(default=None, sa_column=Column(Text))
    reproduction_steps: Optional[str] = Field(default=None, sa_column=Column(Text))
    remediation: Optional[str] = Field(default=None, sa_column=Column(Text))
    raw_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    severity: str = Field(default="medium", index=True)
    cvss_vector: Optional[str] = None
    cve: Optional[str] = None
    references: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = Field(default="draft", index=True)
    content_hash: Optional[str] = Field(default=None, index=True)  # integrity
    confluence_page_id: Optional[str] = None  # set after publish, for idempotent updates
    jira_issue_key: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ---------------- coverage ----------------
class Claim(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    engagement_id: int = Field(foreign_key="engagement.id", index=True)
    target: str  # host ip or CIDR
    claimed_by: str
    expires_at: datetime
    released: bool = False
    created_at: datetime = Field(default_factory=_now)


# ---------------- integrity ledger ----------------
class AuditLog(SQLModel, table=True):
    """Append-only, hash-chained ledger. entry_hash = sha256(prev_hash + canonical
    fields). Any silent edit/delete of findings/evidence breaks the chain."""
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=_now)
    actor: str
    action: str  # create|update|delete
    entity_type: str = Field(index=True)
    entity_id: int = Field(index=True)
    data_hash: str  # sha256 of the entity snapshot after the change
    prev_hash: str
    entry_hash: str = Field(index=True)
