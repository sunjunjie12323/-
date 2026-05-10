import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from loguru import logger
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from app.config import settings
from app.core.exceptions import ForbiddenException, UnauthorizedException


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(BaseModel):
    id: str
    username: str
    hashed_password: str
    role: Role = Role.VIEWER
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserOut(BaseModel):
    id: str
    username: str
    role: Role
    is_active: bool
    created_at: datetime


class TokenData(BaseModel):
    user_id: str
    username: str
    role: Role
    exp: int


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer()

_users_db: Dict[str, User] = {}
_token_blacklist: Set[str] = set()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role.value,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException(detail="Invalid token: missing subject")
        username: str = payload.get("username", "")
        role_str: str = payload.get("role", "viewer")
        try:
            role = Role(role_str)
        except ValueError:
            role = Role.VIEWER
        exp: int = payload.get("exp", 0)
        return TokenData(user_id=user_id, username=username, role=role, exp=exp)
    except JWTError as exc:
        raise UnauthorizedException(detail=f"Invalid token: {exc}")


def blacklist_token(token: str) -> None:
    _token_blacklist.add(token)
    logger.info(f"Token blacklisted, total blacklisted: {len(_token_blacklist)}")


def is_token_blacklisted(token: str) -> bool:
    return token in _token_blacklist


def cleanup_expired_blacklisted_tokens() -> None:
    now = time.time()
    expired = set()
    for token in _token_blacklist:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            if payload.get("exp", 0) < now:
                expired.add(token)
        except JWTError:
            expired.add(token)
    _token_blacklist.difference_update(expired)
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired blacklisted tokens")


def get_user_by_username(username: str) -> Optional[User]:
    return _users_db.get(username)


def get_user_by_id(user_id: str) -> Optional[User]:
    for user in _users_db.values():
        if user.id == user_id:
            return user
    return None


def get_all_users() -> List[User]:
    return list(_users_db.values())


def create_user(username: str, password: str, role: Role = Role.VIEWER) -> User:
    if username in _users_db:
        raise ValueError(f"User '{username}' already exists")
    from uuid import uuid4
    user = User(
        id=uuid4().hex,
        username=username,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    _users_db[username] = user
    logger.info(f"User created: {username} (role={role.value})")
    return user


def update_user_password(username: str, new_password: str) -> bool:
    user = _users_db.get(username)
    if user is None:
        return False
    user.hashed_password = hash_password(new_password)
    logger.info(f"Password updated for user: {username}")
    return True


def deactivate_user(username: str) -> bool:
    user = _users_db.get(username)
    if user is None:
        return False
    user.is_active = False
    logger.info(f"User deactivated: {username}")
    return True


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> User:
    token = credentials.credentials
    if is_token_blacklisted(token):
        raise UnauthorizedException(detail="Token has been revoked")
    token_data = decode_access_token(token)
    user = get_user_by_id(token_data.user_id)
    if user is None:
        raise UnauthorizedException(detail="User not found")
    if not user.is_active:
        raise UnauthorizedException(detail="User account is deactivated")
    return user


def require_role(*allowed_roles: Role):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                detail=f"Role '{current_user.role.value}' not allowed. "
                       f"Required: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker


def create_default_admin() -> User:
    username = settings.DEFAULT_ADMIN_USERNAME
    password = settings.DEFAULT_ADMIN_PASSWORD
    existing = get_user_by_username(username)
    if existing is not None:
        logger.info(f"Default admin user '{username}' already exists")
        return existing
    user = create_user(username=username, password=password, role=Role.ADMIN)
    logger.info(f"Default admin user created: {username}")
    return user
