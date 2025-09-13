from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.item import Item


class ItemRepository(ABC):

    @abstractmethod
    async def create(self, item: Item) -> Item:
        pass

    @abstractmethod
    async def get_by_id(self, item_id: int) -> Optional[Item]:
        pass

    @abstractmethod
    async def get_all(self) -> List[Item]:
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: int) -> List[Item]:
        pass

    @abstractmethod
    async def update(self, item: Item) -> Item:
        pass

    @abstractmethod
    async def delete(self, item_id: int) -> bool:
        pass