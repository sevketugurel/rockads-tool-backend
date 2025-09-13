from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from infrastructure.database.connection import get_async_db
from application.services.dependency_injection import get_item_use_cases
from domain.entities.item import Item

router = APIRouter(prefix="/api/items", tags=["items"])


@router.post("/", response_model=Item)
async def create_item(
    item: Item,
    session: AsyncSession = Depends(get_async_db)
):
    item_use_cases = get_item_use_cases(session)
    return await item_use_cases.create_item(item)


@router.get("/", response_model=List[Item])
async def get_all_items(
    session: AsyncSession = Depends(get_async_db)
):
    item_use_cases = get_item_use_cases(session)
    return await item_use_cases.get_all_items()


@router.get("/{item_id}", response_model=Item)
async def get_item(
    item_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    item_use_cases = get_item_use_cases(session)
    item = await item_use_cases.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/user/{user_id}", response_model=List[Item])
async def get_items_by_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    item_use_cases = get_item_use_cases(session)
    return await item_use_cases.get_items_by_user_id(user_id)


@router.put("/{item_id}", response_model=Item)
async def update_item(
    item_id: int,
    item: Item,
    session: AsyncSession = Depends(get_async_db)
):
    try:
        item.id = item_id
        item_use_cases = get_item_use_cases(session)
        return await item_use_cases.update_item(item)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    try:
        item_use_cases = get_item_use_cases(session)
        success = await item_use_cases.delete_item(item_id)
        if success:
            return {"message": "Item deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Item not found")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))