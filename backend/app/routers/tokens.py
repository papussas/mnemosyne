from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..db import get_session
from ..deps import Principal, get_current_principal
from ..models import ApiToken
from ..schemas import TokenCreate, TokenCreated, TokenRead
from ..security import generate_api_token

router = APIRouter(prefix="/tokens", tags=["api-tokens"])


def _require_user(p: Principal = Depends(get_current_principal)) -> Principal:
    if p.kind != "user":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only user accounts can manage API tokens")
    return p


@router.get("", response_model=list[TokenRead])
def list_tokens(p: Principal = Depends(_require_user), session: Session = Depends(get_session)):
    """Admins see all tokens; contributors see only tokens they created."""
    stmt = select(ApiToken).order_by(ApiToken.id.desc())
    if p.role != "admin":
        stmt = stmt.where(ApiToken.created_by_user_id == p.user_id)
    return session.exec(stmt).all()


@router.post("", response_model=TokenCreated, status_code=status.HTTP_201_CREATED)
def create_token(body: TokenCreate, p: Principal = Depends(_require_user),
                 session: Session = Depends(get_session)):
    """Any user mints a token for their OWN account; it inherits their role."""
    full, prefix, token_hash = generate_api_token()
    expires_at = (datetime.utcnow() + timedelta(days=body.expires_days)
                  if body.expires_days else None)
    row = ApiToken(name=body.name, prefix=prefix, token_hash=token_hash,
                   role=p.role, engagement_id=body.engagement_id,
                   created_by_user_id=p.user_id, expires_at=expires_at)
    session.add(row); session.commit(); session.refresh(row)
    out = TokenRead.model_validate(row, from_attributes=True).model_dump()
    out["token"] = full  # shown once
    return out


@router.delete("/{token_id}")
def revoke_token(token_id: int, p: Principal = Depends(_require_user),
                 session: Session = Depends(get_session)):
    row = session.get(ApiToken, token_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "token not found")
    if p.role != "admin" and row.created_by_user_id != p.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only revoke your own tokens")
    row.revoked = True
    session.add(row); session.commit()
    return {"ok": True, "revoked": True}
