from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from domain.repositories.item_repository import ItemRepository
from domain.entities.item import Item
from infrastructure.database.models import ItemModel


class ItemRepositoryImpl(ItemRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, item: Item) -> Item:
        db_item = ItemModel(
            name=item.name,
            description=item.description,
            price=item.price,
            user_id=item.user_id
        )
        self.session.add(db_item)
        await self.session.commit()
        await self.session.refresh(db_item)
        return Item.model_validate(db_item)

    async def get_by_id(self, item_id: int) -> Optional[Item]:
        result = await self.session.execute(select(ItemModel).where(ItemModel.id == item_id))
        db_item = result.scalar_one_or_none()
        return Item.model_validate(db_item) if db_item else None

    async def get_all(self) -> List[Item]:
        result = await self.session.execute(select(ItemModel))
        db_items = result.scalars().all()
        return [Item.model_validate(db_item) for db_item in db_items]

    async def get_by_user_id(self, user_id: int) -> List[Item]:
        result = await self.session.execute(select(ItemModel).where(ItemModel.user_id == user_id))
        db_items = result.scalars().all()
        return [Item.model_validate(db_item) for db_item in db_items]

    async def update(self, item: Item) -> Item:
        result = await self.session.execute(select(ItemModel).where(ItemModel.id == item.id))
        db_item = result.scalar_one_or_none()
        if db_item:
            db_item.name = item.name
            db_item.description = item.description
            db_item.price = item.price
            db_item.user_id = item.user_id
            await self.session.commit()
            await self.session.refresh(db_item)
            return Item.model_validate(db_item)
        raise ValueError("Item not found")

    async def delete(self, item_id: int) -> bool:
        result = await self.session.execute(select(ItemModel).where(ItemModel.id == item_id))
        db_item = result.scalar_one_or_none()
        if db_item:
            await self.session.delete(db_item)
            await self.session.commit()
            return True
        return False