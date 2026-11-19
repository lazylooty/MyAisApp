from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from typing import Optional, Sequence
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request
import jwt
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import Notification, User

COOKIE_NAME = "access_token"

# Названия ролей из курсового проекта
ROLE_GUEST = "Гость"
ROLE_CLIENT = "Клиент"
ROLE_ASSISTANT = "Помощник риэлтора"
ROLE_REALTOR = "Риэлтор"
ROLE_ADMIN = "Администратор"

STAFF_ROLES = (ROLE_ASSISTANT, ROLE_REALTOR, ROLE_ADMIN)
SENIOR_ROLES = (ROLE_REALTOR, ROLE_ADMIN)


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    parts = stored_hash.split("$", 2)
    if len(parts) != 3 or parts[0] != "pbkdf2_sha256":
        return False
    _, salt, expected_hex = parts
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return hmac.compare_digest(dk.hex(), expected_hex)


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id_user),
        "role": user.role.name if user.role else ROLE_CLIENT,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": now,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> Optional[User]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None

    user = (
        db.query(User)
        .options(
            joinedload(User.role),
            joinedload(User.client_profile),
            joinedload(User.passport),
        )
        .filter(User.id_user == user_id, User.is_active.is_(True))
        .first()
    )
    return user


def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=303,
            headers={"Location": f"/login?error={quote('Необходимо войти в систему')}"},
        )
    return user


def require_roles(allowed_roles: Sequence[str]):
    def _dependency(user: User = Depends(get_current_user)) -> User:
        role_name = user.role.name if user.role else ""
        if role_name not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения этого действия",
            )
        return user

    return _dependency


def get_unread_notifications_count(db: Session, user: Optional[User]) -> int:
    if not user:
        return 0
    return (
        db.query(Notification)
        .filter(Notification.id_user == user.id_user, Notification.is_read.is_(False))
        .count()
    )
