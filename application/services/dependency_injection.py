from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.database.user_repository_impl import UserRepositoryImpl
from infrastructure.database.item_repository_impl import ItemRepositoryImpl
from application.use_cases.user_use_cases import UserUseCases
from application.use_cases.item_use_cases import ItemUseCases


def get_user_use_cases(session: AsyncSession) -> UserUseCases:
    user_repository = UserRepositoryImpl(session)
    return UserUseCases(user_repository)


def get_item_use_cases(session: AsyncSession) -> ItemUseCases:
    item_repository = ItemRepositoryImpl(session)
    return ItemUseCases(item_repository)