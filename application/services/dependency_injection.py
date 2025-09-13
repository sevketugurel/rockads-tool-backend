from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.database.user_repository_impl import UserRepositoryImpl
from infrastructure.database.item_repository_impl import ItemRepositoryImpl
from infrastructure.database.video_repository_impl import VideoRepositoryImpl
from infrastructure.database.transcription_repository_impl import TranscriptionRepositoryImpl
from infrastructure.database.country_repository_impl import CountryRepositoryImpl
from infrastructure.database.translation_repository_impl import TranslationRepositoryImpl, TranslationJobRepositoryImpl
from infrastructure.database.localization_job_repository_impl import LocalizationJobRepositoryImpl
from application.use_cases.user_use_cases import UserUseCases
from application.use_cases.item_use_cases import ItemUseCases
from application.use_cases.video_use_cases import VideoUseCases
from application.use_cases.localization_use_cases import LocalizationUseCases
from application.services.ai.gemini_transcription_service import GeminiTranscriptionService
from application.services.ai.gemini_translation_service import GeminiTranslationService
from application.services.localization_service import LocalizationService


def get_user_use_cases(session: AsyncSession) -> UserUseCases:
    user_repository = UserRepositoryImpl(session)
    return UserUseCases(user_repository)


def get_item_use_cases(session: AsyncSession) -> ItemUseCases:
    item_repository = ItemRepositoryImpl(session)
    return ItemUseCases(item_repository)


def get_video_use_cases(session: AsyncSession) -> VideoUseCases:
    video_repository = VideoRepositoryImpl(session)
    transcription_repository = TranscriptionRepositoryImpl(session)
    transcription_service = GeminiTranscriptionService()
    return VideoUseCases(video_repository, transcription_repository, transcription_service)


def get_localization_use_cases(session: AsyncSession) -> LocalizationUseCases:
    video_repository = VideoRepositoryImpl(session)
    country_repository = CountryRepositoryImpl(session)
    translation_repository = TranslationRepositoryImpl(session)
    localization_job_repository = LocalizationJobRepositoryImpl(session)
    translation_service = GeminiTranslationService()

    localization_service = LocalizationService(
        video_repository=video_repository,
        transcription_repository=TranscriptionRepositoryImpl(session),
        translation_repository=translation_repository,
        country_repository=country_repository,
        localization_job_repository=localization_job_repository,
        translation_service=translation_service
    )

    return LocalizationUseCases(
        video_repository=video_repository,
        country_repository=country_repository,
        translation_repository=translation_repository,
        localization_job_repository=localization_job_repository,
        localization_service=localization_service
    )


class DependencyContainer:
    """Dependency injection container for easier management"""

    def __init__(self, session: AsyncSession = None):
        self._session = session

    def user_use_cases(self) -> UserUseCases:
        return get_user_use_cases(self._session)

    def item_use_cases(self) -> ItemUseCases:
        return get_item_use_cases(self._session)

    def video_use_cases(self) -> VideoUseCases:
        return get_video_use_cases(self._session)

    def localization_use_cases(self) -> LocalizationUseCases:
        return get_localization_use_cases(self._session)