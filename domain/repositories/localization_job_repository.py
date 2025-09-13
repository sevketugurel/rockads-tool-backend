from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.localization_job import LocalizationJob, LocalizationJobStatus


class LocalizationJobRepository(ABC):

    @abstractmethod
    async def create(self, job: LocalizationJob) -> LocalizationJob:
        """Create a new localization job"""
        pass

    @abstractmethod
    async def get_by_id(self, job_id: int) -> Optional[LocalizationJob]:
        """Get localization job by ID"""
        pass

    @abstractmethod
    async def get_by_video_id(self, video_id: int) -> List[LocalizationJob]:
        """Get all localization jobs for a video"""
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: int) -> List[LocalizationJob]:
        """Get all localization jobs for a user"""
        pass

    @abstractmethod
    async def get_all(self) -> List[LocalizationJob]:
        """Get all localization jobs"""
        pass

    @abstractmethod
    async def get_by_status(self, status: LocalizationJobStatus) -> List[LocalizationJob]:
        """Get jobs by status"""
        pass

    @abstractmethod
    async def update(self, job: LocalizationJob) -> LocalizationJob:
        """Update localization job"""
        pass

    @abstractmethod
    async def update_status(self, job_id: int, status: LocalizationJobStatus) -> bool:
        """Update job status"""
        pass

    @abstractmethod
    async def update_progress(self, job_id: int, progress: float) -> bool:
        """Update job progress percentage"""
        pass

    @abstractmethod
    async def delete(self, job_id: int) -> bool:
        """Delete localization job"""
        pass