from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from domain.repositories.user_repository import UserRepository
from domain.entities.user import User
from infrastructure.database.models import UserModel


class UserRepositoryImpl(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user: User) -> User:
        db_user = UserModel(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active
        )
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return User.model_validate(db_user)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        db_user = result.scalar_one_or_none()
        return User.model_validate(db_user) if db_user else None

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(select(UserModel).where(UserModel.email == email))
        db_user = result.scalar_one_or_none()
        return User.model_validate(db_user) if db_user else None

    async def get_all(self) -> List[User]:
        result = await self.session.execute(select(UserModel))
        db_users = result.scalars().all()
        return [User.model_validate(db_user) for db_user in db_users]

    async def update(self, user: User) -> User:
        result = await self.session.execute(select(UserModel).where(UserModel.id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user:
            db_user.username = user.username
            db_user.email = user.email
            db_user.full_name = user.full_name
            db_user.is_active = user.is_active
            await self.session.commit()
            await self.session.refresh(db_user)
            return User.model_validate(db_user)
        raise ValueError("User not found")

    async def delete(self, user_id: int) -> bool:
        result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        db_user = result.scalar_one_or_none()
        if db_user:
            await self.session.delete(db_user)
            await self.session.commit()
            return True
        return False