from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import verify_password, create_access_token, get_current_user
from app.repositories.user_repo import UserRepository
from app.schemas.response import ApiResponse

router = APIRouter()


@router.post("/login", response_model=ApiResponse[dict])
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    repo = UserRepository(db)
    user = await repo.get_by_username(form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    token = create_access_token(user.id, user.role)
    await repo.update_last_login(user.id)
    return ApiResponse.ok(data={
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "display_name": user.display_name,
        "role": user.role,
    })


@router.get("/me", response_model=ApiResponse[dict])
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    repo = UserRepository(db)
    user = await repo.get_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ApiResponse.ok(data={
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "department": user.department,
        "role": user.role,
    })
