from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, or_, select

from ..config import settings
from ..db import get_session
from ..deps import Principal, current_admin, get_current_principal
from ..models import User, _now
from ..schemas import (LoginRequest, PasswordChange, PasswordReset, TwoFACode,
                       UserCreate, UserRead, UserUpdate)
from ..ratelimit import hit
from ..security import (create_access_token, hash_password, needs_rehash,
                        new_totp_secret, totp_provisioning_uri, verify_password,
                        verify_totp)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(resp: Response, username: str) -> None:
    resp.set_cookie(
        key=settings.cookie_name, value=create_access_token(username),
        httponly=True, secure=settings.cookie_secure, samesite="lax",
        max_age=settings.access_token_expire_minutes * 60, path="/",
    )


@router.post("/login", response_model=UserRead)
def login(body: LoginRequest, resp: Response, request: Request, session: Session = Depends(get_session)):
    ip = request.client.host if request.client else "unknown"
    hit(f"login-ip:{ip}", max_hits=15, window=300)
    hit(f"login-id:{body.identifier}", max_hits=6, window=300)
    user = session.exec(
        select(User).where(or_(User.username == body.identifier, User.email == body.identifier))
    ).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    if user.totp_enabled:
        if not body.otp:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "otp_required")
        if not verify_totp(user.totp_secret or "", body.otp):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid 2FA code")
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(body.password)
        session.add(user); session.commit()
    _set_cookie(resp, user.username)
    return user


@router.post("/logout")
def logout(resp: Response):
    resp.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.get("/me")
def me(p: Principal = Depends(get_current_principal), session: Session = Depends(get_session)):
    out = {"kind": p.kind, "role": p.role, "actor": p.actor,
           "engagement_id": p.engagement_id}
    if p.kind == "user" and p.user_id:
        u = session.get(User, p.user_id)
        if u:
            out["user"] = UserRead.model_validate(u, from_attributes=True).model_dump()
    return out


def _require_user(p: Principal = Depends(get_current_principal)) -> Principal:
    if p.kind != "user":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only human accounts can manage 2FA")
    return p


@router.post("/2fa/setup")
def twofa_setup(p: Principal = Depends(_require_user), session: Session = Depends(get_session)):
    user = session.get(User, p.user_id)
    secret = new_totp_secret()
    user.totp_secret = secret  # staged; not enabled until confirmed
    session.add(user); session.commit()
    return {"secret": secret, "otpauth_uri": totp_provisioning_uri(secret, user.email)}


@router.post("/2fa/enable")
def twofa_enable(body: TwoFACode, p: Principal = Depends(_require_user),
                 session: Session = Depends(get_session)):
    user = session.get(User, p.user_id)
    if not user.totp_secret or not verify_totp(user.totp_secret, body.otp):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid 2FA code")
    user.totp_enabled = True
    session.add(user); session.commit()
    return {"ok": True, "totp_enabled": True}


@router.post("/2fa/disable")
def twofa_disable(body: TwoFACode, p: Principal = Depends(_require_user),
                  session: Session = Depends(get_session)):
    user = session.get(User, p.user_id)
    if not user.totp_enabled or not verify_totp(user.totp_secret or "", body.otp):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid 2FA code")
    user.totp_enabled = False
    user.totp_secret = None
    session.add(user); session.commit()
    return {"ok": True, "totp_enabled": False}


@router.get("/users", response_model=list[UserRead])
def list_users(_: Principal = Depends(current_admin), session: Session = Depends(get_session)):
    return session.exec(select(User).order_by(User.id)).all()


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _: Principal = Depends(current_admin),
                session: Session = Depends(get_session)):
    exists = session.exec(
        select(User).where(or_(User.username == body.username, User.email == body.email))
    ).first()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "username or email already exists")
    if len(body.password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "password must be at least 8 characters")
    user = User(email=body.email, username=body.username, full_name=body.full_name,
                role=body.role.value, hashed_password=hash_password(body.password))
    session.add(user); session.commit(); session.refresh(user)
    return user


@router.patch("/users/{uid}", response_model=UserRead)
def update_user(uid: int, body: UserUpdate, _: Principal = Depends(current_admin),
                session: Session = Depends(get_session)):
    user = session.get(User, uid)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    data = body.model_dump(exclude_unset=True)
    if "role" in data and data["role"] is not None:
        data["role"] = data["role"].value if hasattr(data["role"], "value") else data["role"]
    for k, v in data.items():
        setattr(user, k, v)
    user.updated_at = _now()
    session.add(user); session.commit(); session.refresh(user)
    return user


@router.post("/users/{uid}/password")
def admin_reset_password(uid: int, body: PasswordReset, _: Principal = Depends(current_admin),
                         session: Session = Depends(get_session)):
    user = session.get(User, uid)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    if len(body.new_password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "password must be at least 8 characters")
    user.hashed_password = hash_password(body.new_password)
    user.updated_at = _now()
    session.add(user); session.commit()
    return {"ok": True}


@router.post("/change-password")
def change_password(body: PasswordChange, p: Principal = Depends(get_current_principal),
                    session: Session = Depends(get_session)):
    if p.kind != "user":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only user accounts can change a password")
    user = session.get(User, p.user_id)
    if not user or not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "new password must be at least 8 characters")
    user.hashed_password = hash_password(body.new_password)
    user.updated_at = _now()
    session.add(user); session.commit()
    return {"ok": True}
