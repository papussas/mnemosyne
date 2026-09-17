from enum import Enum


class Role(str, Enum):
    admin = "admin"
    contributor = "contributor"


class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class FindingStatus(str, Enum):
    draft = "draft"
    open = "open"
    confirmed = "confirmed"
    remediated = "remediated"
    retested = "retested"
    risk_accepted = "risk_accepted"
    false_positive = "false_positive"


class ServiceType(str, Enum):
    http = "http"
    https = "https"
    ssh = "ssh"
    smb = "smb"
    ftp = "ftp"
    rdp = "rdp"
    dns = "dns"
    smtp = "smtp"
    mysql = "mysql"
    mssql = "mssql"
    postgres = "postgres"
    other = "other"


class CredType(str, Enum):
    password = "password"
    ntlm_hash = "ntlm_hash"
    kerberos = "kerberos"
    ssh_key = "ssh_key"
    token = "token"
    other = "other"


class WorksStatus(str, Enum):
    works = "works"
    failed = "failed"
    untested = "untested"


class LootType(str, Enum):
    file = "file"
    config = "config"
    hash = "hash"
    other = "other"


class AttachmentTarget(str, Enum):
    service = "service"
    finding = "finding"
    evidence = "evidence"
    loot = "loot"
    host = "host"


class ScopeRuleType(str, Enum):
    include = "include"
    exclude = "exclude"


class AuditAction(str, Enum):
    create = "create"
    update = "update"
    delete = "delete"
