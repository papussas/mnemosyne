from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from .config import settings
from .db import get_session
from .models import ApiToken, User
from .security import decode_access_token, hash_api_token

_ROLE_RANK = {"contributor": 0, "admin": 1}


@dataclass
class Principal:
    kind: str            # "user" | "agent"
    role: str
    actor: str           # "user:alice" | "agent:aria-01"
    user_id: Optional[int] = None
    token_id: Optional[int] = None
    engagement_id: Optional[int] = None  # agent-token scope, if any


def _bearer_or_cookie_jwt(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(settings.cookie_name)


def get_current_principal(request: Request,
                          session: Session = Depends(get_session)) -> Principal:
    # 1) Human session (JWT via cookie or bearer)
    token = _bearer_or_cookie_jwt(request)
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("typ") == "session":
            user = session.exec(select(User).where(User.username == payload.get("sub"))).first()
            if user and user.is_active:
                return Principal(kind="user", role=user.role,
                                 actor=f"user:{user.username}", user_id=user.id)

    # 2) Agent API token (X-API-Key)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        row = session.exec(select(ApiToken).where(ApiToken.token_hash == hash_api_token(api_key))).first()
        if row and not row.revoked:
            if row.expires_at and row.expires_at < datetime.utcnow():
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API token expired")
            row.last_used_at = datetime.utcnow()
            session.add(row); session.commit()
            return Principal(kind="agent", role=row.role, actor=f"agent:{row.name}",
                             token_id=row.id, engagement_id=row.engagement_id)

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                        headers={"WWW-Authenticate": "Bearer"})


def require_role(minimum: str):
    def _dep(p: Principal = Depends(get_current_principal)) -> Principal:
        if _ROLE_RANK.get(p.role, -1) < _ROLE_RANK[minimum]:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Requires role '{minimum}' or higher")
        return p
    return _dep


# convenience deps — with only admin + contributor, both can read and write;
# admin additionally manages users and other people's tokens.
def current_reader(p: Principal = Depends(require_role("contributor"))) -> Principal:
    return p


def current_writer(p: Principal = Depends(require_role("contributor"))) -> Principal:
    return p


def current_admin(p: Principal = Depends(require_role("admin"))) -> Principal:
    return p
