import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set
from uuid import uuid4

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


class HTTPBearer401(HTTPBearer):
    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        try:
            return await super().__call__(request)
        except Exception:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

security_scheme = HTTPBearer401()

_users_db: Dict[str, User] = {}
_token_blacklist: Dict[str, float] = {}

_BLACKLIST_CLEANUP_INTERVAL = 300
_last_cleanup = time.time()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role.value,
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key_resolved, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.secret_key_resolved, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException(detail="无效令牌: 缺少用户标识")
        username: str = payload.get("username", "")
        role_str: str = payload.get("role", "viewer")
        try:
            role = Role(role_str)
        except ValueError:
            role = Role.VIEWER
        exp: int = payload.get("exp", 0)
        return TokenData(user_id=user_id, username=username, role=role, exp=exp)
    except JWTError as exc:
        raise UnauthorizedException(detail=f"无效令牌: {exc}")


def blacklist_token(token: str) -> None:
    try:
        payload = jwt.decode(token, settings.secret_key_resolved, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp", 0)
    except JWTError:
        exp = time.time() + 3600
    _token_blacklist[token] = float(exp)
    logger.info(f"Token blacklisted, total blacklisted: {len(_token_blacklist)}")
    _maybe_cleanup_blacklist()


def is_token_blacklisted(token: str) -> bool:
    if token in _token_blacklist:
        exp = _token_blacklist.get(token, 0)
        if exp > time.time():
            return True
        else:
            _token_blacklist.pop(token, None)
            return False
    return False


def _maybe_cleanup_blacklist() -> None:
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < _BLACKLIST_CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    cleanup_expired_blacklisted_tokens()


def cleanup_expired_blacklisted_tokens() -> None:
    now = time.time()
    expired_keys = [k for k, v in _token_blacklist.items() if v < now]
    for k in expired_keys:
        _token_blacklist.pop(k, None)
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired blacklisted tokens, remaining: {len(_token_blacklist)}")


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
        raise ValueError(f"用户名 '{username}' 已存在")
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
        raise UnauthorizedException(detail="令牌已被撤销，请重新登录")
    token_data = decode_access_token(token)
    user = get_user_by_id(token_data.user_id)
    if user is None:
        raise UnauthorizedException(detail="用户不存在")
    if not user.is_active:
        raise UnauthorizedException(detail="用户账号已被停用")
    return user


def require_role(*allowed_roles: Role):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                detail=f"权限不足: 当前角色 '{current_user.role.value}'，"
                       f"需要: {[r.value for r in allowed_roles]}"
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
