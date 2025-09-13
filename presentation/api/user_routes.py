from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from infrastructure.database.connection import get_async_db
from application.services.dependency_injection import get_user_use_cases
from domain.entities.user import User

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("/", response_model=User)
async def create_user(
    user: User,
    session: AsyncSession = Depends(get_async_db)
):
    try:
        user_use_cases = get_user_use_cases(session)
        return await user_use_cases.create_user(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[User])
async def get_all_users(
    session: AsyncSession = Depends(get_async_db)
):
    user_use_cases = get_user_use_cases(session)
    return await user_use_cases.get_all_users()


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    user_use_cases = get_user_use_cases(session)
    user = await user_use_cases.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/email/{email}", response_model=User)
async def get_user_by_email(
    email: str,
    session: AsyncSession = Depends(get_async_db)
):
    user_use_cases = get_user_use_cases(session)
    user = await user_use_cases.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user: User,
    session: AsyncSession = Depends(get_async_db)
):
    try:
        user.id = user_id
        user_use_cases = get_user_use_cases(session)
        return await user_use_cases.update_user(user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    try:
        user_use_cases = get_user_use_cases(session)
        success = await user_use_cases.delete_user(user_id)
        if success:
            return {"message": "User deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))