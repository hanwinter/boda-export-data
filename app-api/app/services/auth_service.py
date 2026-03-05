from __future__ import annotations

from dataclasses import dataclass

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


@dataclass
class UserRecord:
    username: str
    password_hash: str
    role: str
    is_active: bool


USERS: dict[str, UserRecord] = {
    "admin": UserRecord(
        username="admin",
        password_hash=pwd_context.hash("admin123"),
        role="admin",
        is_active=True,
    ),
    "viewer": UserRecord(
        username="viewer",
        password_hash=pwd_context.hash("viewer123"),
        role="viewer",
        is_active=True,
    ),
}


def authenticate_user(username: str, password: str) -> UserRecord | None:
    user = USERS.get(username)
    if not user or not user.is_active:
        return None
    if not pwd_context.verify(password, user.password_hash):
        return None
    return user


def get_user(username: str) -> UserRecord | None:
    return USERS.get(username)


def list_users() -> list[UserRecord]:
    return sorted(USERS.values(), key=lambda x: x.username)


def create_user(username: str, password: str, role: str) -> UserRecord:
    if username in USERS:
        raise ValueError("用户已存在")
    if role not in {"admin", "viewer"}:
        raise ValueError("角色非法")

    record = UserRecord(
        username=username,
        password_hash=pwd_context.hash(password),
        role=role,
        is_active=True,
    )
    USERS[username] = record
    return record


def set_user_active(username: str, is_active: bool) -> UserRecord:
    user = USERS.get(username)
    if not user:
        raise ValueError("用户不存在")
    user.is_active = is_active
    return user


def reset_password(username: str, new_password: str) -> UserRecord:
    user = USERS.get(username)
    if not user:
        raise ValueError("用户不存在")
    user.password_hash = pwd_context.hash(new_password)
    return user
