"""Hash-chained, append-only audit ledger + per-record content hashing.

Every mutation to an integrity-tracked entity (findings, evidence) appends an
AuditLog row whose entry_hash chains the previous row. Tampering with a finding
without a matching, correctly-chained ledger entry is detectable by verify_chain().
"""
import hashlib
import json
from datetime import datetime

from sqlmodel import Session, select

from .models import AuditLog

GENESIS = "0" * 64
_VOLATILE = {"content_hash", "updated_at"}


def canonical_hash(data: dict) -> str:
    payload = {k: v for k, v in data.items() if k not in _VOLATILE}
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _entry_hash(prev_hash: str, ts: datetime, actor: str, action: str,
                entity_type: str, entity_id: int, data_hash: str) -> str:
    material = f"{prev_hash}|{ts.isoformat()}|{actor}|{action}|{entity_type}|{entity_id}|{data_hash}"
    return hashlib.sha256(material.encode()).hexdigest()


def record(session: Session, *, actor: str, action: str, entity_type: str,
           entity_id: int, snapshot: dict) -> AuditLog:
    """Append a chained ledger entry. Caller commits."""
    data_hash = canonical_hash(snapshot)
    last = session.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    prev_hash = last.entry_hash if last else GENESIS
    ts = datetime.utcnow()
    entry = AuditLog(
        ts=ts, actor=actor, action=action, entity_type=entity_type,
        entity_id=entity_id, data_hash=data_hash, prev_hash=prev_hash,
        entry_hash=_entry_hash(prev_hash, ts, actor, action, entity_type, entity_id, data_hash),
    )
    session.add(entry)
    return entry


def verify_chain(session: Session) -> dict:
    """Re-walk the ledger; report whether the chain is intact and where it breaks."""
    rows = session.exec(select(AuditLog).order_by(AuditLog.id.asc())).all()
    prev = GENESIS
    for row in rows:
        expected = _entry_hash(prev, row.ts, row.actor, row.action,
                               row.entity_type, row.entity_id, row.data_hash)
        if row.prev_hash != prev or row.entry_hash != expected:
            return {"ok": False, "entries": len(rows), "broken_at_id": row.id,
                    "reason": "prev_hash mismatch" if row.prev_hash != prev else "entry_hash mismatch"}
        prev = row.entry_hash
    return {"ok": True, "entries": len(rows), "head": prev if rows else GENESIS}
