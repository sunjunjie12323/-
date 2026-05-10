from datetime import datetime
from typing import List

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
    require_role,
    update_user_password,
    verify_password,
)
from app.core.exceptions import ForbiddenException, UnauthorizedException, ValidationException

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    password: str = Field(..., min_length=6, max_length=128)
    role: Role = Role.VIEWER


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    from app.core.auth import get_user_by_username
    user = get_user_by_username(data.username)
    if user is None:
        raise UnauthorizedException(detail="Invalid username or password")
    if not user.is_active:
        raise UnauthorizedException(detail="User account is deactivated")
    if not verify_password(data.password, user.hashed_password):
        raise UnauthorizedException(detail="Invalid username or password")
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
    try:
        user = create_user(
            username=data.username,
            password=data.password,
            role=data.role,
        )
    except ValueError as exc:
        raise ValidationException(detail=str(exc))
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
        raise ValidationException(detail="Current password is incorrect")
    if data.current_password == data.new_password:
        raise ValidationException(detail="New password must be different from current password")
    update_user_password(current_user.username, data.new_password)
    return {"message": "Password updated successfully"}


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
):
    token = credentials.credentials
    blacklist_token(token)
    logger.info(f"User logged out: {current_user.username}")
    return {"message": "Logged out successfully"}


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
