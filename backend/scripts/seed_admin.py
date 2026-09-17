"""Create the first admin user from .env (idempotent)."""
from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.models import User
from app.security import hash_password


def main() -> None:
    with Session(engine) as session:
        existing = session.exec(
            select(User).where(User.username == settings.admin_username)
        ).first()
        if existing:
            print(f"admin '{settings.admin_username}' already exists (id={existing.id})")
            return
        user = User(
            email=settings.admin_email,
            username=settings.admin_username,
            full_name="Administrator",
            hashed_password=hash_password(settings.admin_password),
            role="admin",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"created admin '{user.username}' (id={user.id})")


if __name__ == "__main__":
    main()
