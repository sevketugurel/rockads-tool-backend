from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.transcription import Transcription, TranscriptionStatus


class TranscriptionRepository(ABC):

    @abstractmethod
    async def create(self, transcription: Transcription) -> Transcription:
        """Create a new transcription record"""
        pass

    @abstractmethod
    async def get_by_id(self, transcription_id: int) -> Optional[Transcription]:
        """Get transcription by ID"""
        pass

    @abstractmethod
    async def get_by_video_id(self, video_id: int) -> Optional[Transcription]:
        """Get transcription by video ID"""
        pass

    @abstractmethod
    async def get_all(self) -> List[Transcription]:
        """Get all transcriptions"""
        pass

    @abstractmethod
    async def get_by_status(self, status: TranscriptionStatus) -> List[Transcription]:
        """Get transcriptions by status"""
        pass

    @abstractmethod
    async def update(self, transcription: Transcription) -> Transcription:
        """Update transcription"""
        pass

    @abstractmethod
    async def update_status(self, transcription_id: int, status: TranscriptionStatus) -> bool:
        """Update transcription status"""
        pass

    @abstractmethod
    async def delete(self, transcription_id: int) -> bool:
        """Delete transcription"""
        pass