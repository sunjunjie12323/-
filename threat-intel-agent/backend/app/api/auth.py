import re
import time
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel, Field

from app.core.auth import (
    Role,
    User,
    UserOut,
    blacklist_token,
    create_access_token,
    create_user,
    get_all_users,
    get_current_user,
    get_user_by_username,
    hash_password,
    require_role,
    update_user_password,
    verify_password,
)
from app.core.exceptions import ForbiddenException, UnauthorizedException, ValidationException


router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_ATTEMPTS: dict = {}
_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_SECONDS = 300


def _check_login_lockout(username: str):
    record = _LOGIN_ATTEMPTS.get(username)
    if record is None:
        return
    attempts, locked_until = record
    if locked_until and time.time() < locked_until:
        remaining = int(locked_until - time.time())
        raise ForbiddenException(detail=f"账号已锁定，请{remaining}秒后重试")
    if locked_until and time.time() >= locked_until:
        del _LOGIN_ATTEMPTS[username]


def _record_failed_login(username: str):
    record = _LOGIN_ATTEMPTS.get(username, [0, None])
    record[0] += 1
    if record[0] >= _MAX_LOGIN_ATTEMPTS:
        record[1] = time.time() + _LOCKOUT_SECONDS
        logger.warning(f"Account locked due to brute force: {username}")
    _LOGIN_ATTEMPTS[username] = record


def _clear_failed_logins(username: str):
    _LOGIN_ATTEMPTS.pop(username, None)


def _validate_password_strength(password: str):
    if len(password) < 8:
        raise ValidationException(detail="密码长度至少8位")
    if not re.search(r"[A-Za-z]", password):
        raise ValidationException(detail="密码必须包含字母")
    if not re.search(r"[0-9]", password):
        raise ValidationException(detail="密码必须包含数字")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    password: str = Field(..., min_length=8, max_length=128)
    role: Role = Role.VIEWER


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    _check_login_lockout(data.username)
    user = get_user_by_username(data.username)
    if user is None:
        _record_failed_login(data.username)
        raise UnauthorizedException(detail="用户名或密码错误")
    if not user.is_active:
        raise UnauthorizedException(detail="用户账号已被停用")
    if not verify_password(data.password, user.hashed_password):
        _record_failed_login(data.username)
        raise UnauthorizedException(detail="用户名或密码错误")
    _clear_failed_logins(data.username)
    access_token = create_access_token(user)
    logger.info(f"User logged in: {data.username}")
    return LoginResponse(
        access_token=access_token,
        user=UserOut(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    data: RegisterRequest,
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    _validate_password_strength(data.password)
    existing = get_user_by_username(data.username)
    if existing is not None:
        raise ValidationException(detail=f"用户名 '{data.username}' 已存在")
    try:
        user = create_user(
            username=data.username,
            password=data.password,
            role=data.role,
        )
    except ValueError as exc:
        raise ValidationException(detail=str(exc))
    except Exception as exc:
        logger.error(f"Failed to create user: {exc}")
        raise ValidationException(detail=f"创建用户失败: {str(exc)}")
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.put("/password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise ValidationException(detail="当前密码不正确")
    if data.current_password == data.new_password:
        raise ValidationException(detail="新密码不能与当前密码相同")
    _validate_password_strength(data.new_password)
    update_user_password(current_user.username, data.new_password)
    return {"message": "密码修改成功"}


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
):
    token = credentials.credentials
    blacklist_token(token)
    logger.info(f"User logged out: {current_user.username}")
    return {"message": "退出登录成功"}


@router.get("/users", response_model=List[UserOut])
async def list_users(current_user: User = Depends(require_role(Role.ADMIN))):
    users = get_all_users()
    return [
        UserOut(
            id=u.id,
            username=u.username,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]
