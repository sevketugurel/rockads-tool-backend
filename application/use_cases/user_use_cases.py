from typing import List, Optional
from domain.entities.user import User
from domain.repositories.user_repository import UserRepository


class UserUseCases:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def create_user(self, user: User) -> User:
        existing_user = await self.user_repository.get_by_email(user.email)
        if existing_user:
            raise ValueError("User with this email already exists")
        return await self.user_repository.create(user)

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        return await self.user_repository.get_by_id(user_id)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        return await self.user_repository.get_by_email(email)

    async def get_all_users(self) -> List[User]:
        return await self.user_repository.get_all()

    async def update_user(self, user: User) -> User:
        existing_user = await self.user_repository.get_by_id(user.id)
        if not existing_user:
            raise ValueError("User not found")
        return await self.user_repository.update(user)

    async def delete_user(self, user_id: int) -> bool:
        existing_user = await self.user_repository.get_by_id(user_id)
        if not existing_user:
            raise ValueError("User not found")
        return await self.user_repository.delete(user_id)