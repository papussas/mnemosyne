from fastapi import APIRouter

from ..constants import (CredType, FindingStatus, LootType, Role, ScopeRuleType,
                        ServiceType, Severity, WorksStatus)

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/enums")
def enums():
    """Enum vocabularies for frontend dropdowns."""
    return {name: [e.value for e in enum] for name, enum in {
        "role": Role, "severity": Severity, "finding_status": FindingStatus,
        "service_type": ServiceType, "cred_type": CredType,
        "works_status": WorksStatus, "loot_type": LootType,
        "scope_rule_type": ScopeRuleType,
    }.items()}
