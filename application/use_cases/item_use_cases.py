from typing import List, Optional
from domain.entities.item import Item
from domain.repositories.item_repository import ItemRepository


class ItemUseCases:
    def __init__(self, item_repository: ItemRepository):
        self.item_repository = item_repository

    async def create_item(self, item: Item) -> Item:
        return await self.item_repository.create(item)

    async def get_item_by_id(self, item_id: int) -> Optional[Item]:
        return await self.item_repository.get_by_id(item_id)

    async def get_all_items(self) -> List[Item]:
        return await self.item_repository.get_all()

    async def get_items_by_user_id(self, user_id: int) -> List[Item]:
        return await self.item_repository.get_by_user_id(user_id)

    async def update_item(self, item: Item) -> Item:
        existing_item = await self.item_repository.get_by_id(item.id)
        if not existing_item:
            raise ValueError("Item not found")
        return await self.item_repository.update(item)

    async def delete_item(self, item_id: int) -> bool:
        existing_item = await self.item_repository.get_by_id(item_id)
        if not existing_item:
            raise ValueError("Item not found")
        return await self.item_repository.delete(item_id)