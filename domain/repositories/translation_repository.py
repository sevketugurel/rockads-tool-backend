from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.translation import Translation, TranslationJob, TranslationStatus


class TranslationRepository(ABC):
    """Abstract repository for Translation entities"""

    @abstractmethod
    async def create(self, translation: Translation) -> Translation:
        """Create a new translation"""
        pass

    @abstractmethod
    async def get_by_id(self, translation_id: int) -> Optional[Translation]:
        """Get translation by ID"""
        pass

    @abstractmethod
    async def get_by_video_id(self, video_id: int) -> List[Translation]:
        """Get all translations for a video"""
        pass

    @abstractmethod
    async def get_by_video_and_country(self, video_id: int, country_id: int) -> Optional[Translation]:
        """Get translation for specific video and country combination"""
        pass

    @abstractmethod
    async def get_by_country_id(self, country_id: int) -> List[Translation]:
        """Get all translations for a country"""
        pass

    @abstractmethod
    async def get_by_status(self, status: TranslationStatus) -> List[Translation]:
        """Get translations by status"""
        pass

    @abstractmethod
    async def get_by_transcription_id(self, transcription_id: int) -> List[Translation]:
        """Get translations by transcription ID"""
        pass

    @abstractmethod
    async def update(self, translation: Translation) -> Translation:
        """Update existing translation"""
        pass

    @abstractmethod
    async def update_status(self, translation_id: int, status: TranslationStatus) -> bool:
        """Update translation status"""
        pass

    @abstractmethod
    async def delete(self, translation_id: int) -> bool:
        """Delete translation by ID"""
        pass

    @abstractmethod
    async def get_completed_translations(self, limit: Optional[int] = None) -> List[Translation]:
        """Get completed translations, optionally limited"""
        pass

    @abstractmethod
    async def get_failed_translations(self, limit: Optional[int] = None) -> List[Translation]:
        """Get failed translations for retry, optionally limited"""
        pass


class TranslationJobRepository(ABC):
    """Abstract repository for TranslationJob entities"""

    @abstractmethod
    async def create(self, job: TranslationJob) -> TranslationJob:
        """Create a new translation job"""
        pass

    @abstractmethod
    async def get_by_id(self, job_id: int) -> Optional[TranslationJob]:
        """Get translation job by ID"""
        pass

    @abstractmethod
    async def get_by_video_id(self, video_id: int) -> List[TranslationJob]:
        """Get translation jobs for a video"""
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: int) -> List[TranslationJob]:
        """Get translation jobs for a user"""
        pass

    @abstractmethod
    async def get_by_status(self, status: str) -> List[TranslationJob]:
        """Get translation jobs by status"""
        pass

    @abstractmethod
    async def update(self, job: TranslationJob) -> TranslationJob:
        """Update existing translation job"""
        pass

    @abstractmethod
    async def delete(self, job_id: int) -> bool:
        """Delete translation job by ID"""
        pass

    @abstractmethod
    async def get_active_jobs(self) -> List[TranslationJob]:
        """Get all active translation jobs"""
        pass