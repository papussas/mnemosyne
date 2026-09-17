from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from .constants import (CredType, FindingStatus, LootType, Role, ScopeRuleType,
                        ServiceType, Severity, WorksStatus)


# ---- auth ----
class LoginRequest(BaseModel):
    identifier: str  # username or email
    password: str
    otp: Optional[str] = None


class UserRead(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    totp_enabled: bool


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    role: Role = Role.contributor


class TwoFACode(BaseModel):
    otp: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ---- api tokens ----
class TokenCreate(BaseModel):
    name: str
    engagement_id: Optional[int] = None
    expires_days: Optional[int] = None
    # role is not accepted here — an agent token inherits the creating user's role.


class TokenRead(BaseModel):
    id: int
    name: str
    prefix: str
    role: str
    engagement_id: Optional[int]
    expires_at: Optional[datetime]
    revoked: bool
    last_used_at: Optional[datetime]
    created_at: datetime


class TokenCreated(TokenRead):
    token: str  # full token, shown once


# ---- infra / core CRUD ----
class ClientCreate(BaseModel):
    name: str
    description: Optional[str] = None


class AssetUpdate(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class EngagementCreate(BaseModel):
    client_id: int
    name: str
    description: Optional[str] = None
    status: str = "active"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class EngagementUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ScopeCreate(BaseModel):
    engagement_id: int
    rule_type: ScopeRuleType = ScopeRuleType.include
    pattern: str
    note: Optional[str] = None


class ScopeUpdate(BaseModel):
    rule_type: Optional[ScopeRuleType] = None
    pattern: Optional[str] = None
    note: Optional[str] = None


class HostCreate(BaseModel):
    engagement_id: int
    ip: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    tags: list[str] = []
    in_scope: bool = True
    notes: Optional[str] = None


class HostUpdate(BaseModel):
    ip: Optional[str] = None
    hostname: Optional[str] = None
    os: Optional[str] = None
    tags: Optional[list[str]] = None
    in_scope: Optional[bool] = None
    notes: Optional[str] = None


class ServiceCreate(BaseModel):
    host_id: int
    port: int
    proto: str = "tcp"
    service_type: ServiceType = ServiceType.other
    product: Optional[str] = None
    version: Optional[str] = None
    banner: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class ServiceUpdate(BaseModel):
    port: Optional[int] = None
    proto: Optional[str] = None
    service_type: Optional[ServiceType] = None
    product: Optional[str] = None
    version: Optional[str] = None
    banner: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class EvidenceCreate(BaseModel):
    host_id: Optional[int] = None
    service_id: Optional[int] = None
    finding_id: Optional[int] = None
    title: str
    content: Optional[str] = None
    source: Optional[str] = None


class EvidenceUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None


class CredentialCreate(BaseModel):
    engagement_id: int
    cred_type: CredType = CredType.password
    username: Optional[str] = None
    secret: Optional[str] = None
    realm: Optional[str] = None
    source: Optional[str] = None
    validated: bool = False
    notes: Optional[str] = None


class CredentialUpdate(BaseModel):
    cred_type: Optional[CredType] = None
    username: Optional[str] = None
    secret: Optional[str] = None
    realm: Optional[str] = None
    source: Optional[str] = None
    validated: Optional[bool] = None
    notes: Optional[str] = None


class WorksOnCreate(BaseModel):
    credential_id: int
    service_id: int
    status: WorksStatus = WorksStatus.untested
    note: Optional[str] = None
    tested_at: Optional[datetime] = None


class LootCreate(BaseModel):
    engagement_id: int
    host_id: Optional[int] = None
    service_id: Optional[int] = None
    loot_type: LootType = LootType.other
    title: str
    content: Optional[str] = None


class LootUpdate(BaseModel):
    loot_type: Optional[LootType] = None
    title: Optional[str] = None
    content: Optional[str] = None


class FindingTemplateCreate(BaseModel):
    client_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    business_impact: Optional[str] = None
    remediation: Optional[str] = None
    references: list[str] = []
    default_severity: Severity = Severity.medium
    category: Optional[str] = None


class FindingTemplateUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    business_impact: Optional[str] = None
    remediation: Optional[str] = None
    references: Optional[list[str]] = None
    default_severity: Optional[Severity] = None
    category: Optional[str] = None


class FindingCreate(BaseModel):
    engagement_id: int
    service_id: int  # required anchor
    template_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    business_impact: Optional[str] = None
    reproduction_steps: Optional[str] = None
    remediation: Optional[str] = None
    raw_notes: Optional[str] = None
    severity: Severity = Severity.medium
    cvss_vector: Optional[str] = None
    cve: Optional[str] = None
    references: list[str] = []
    status: FindingStatus = FindingStatus.draft


class FindingUpdate(BaseModel):
    template_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    business_impact: Optional[str] = None
    reproduction_steps: Optional[str] = None
    remediation: Optional[str] = None
    raw_notes: Optional[str] = None
    severity: Optional[Severity] = None
    cvss_vector: Optional[str] = None
    cve: Optional[str] = None
    references: Optional[list[str]] = None
    status: Optional[FindingStatus] = None


class ClaimCreate(BaseModel):
    engagement_id: int
    target: str
    ttl_minutes: int = 120
