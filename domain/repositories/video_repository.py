from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.video import Video, VideoStatus


class VideoRepository(ABC):

    @abstractmethod
    async def create(self, video: Video) -> Video:
        """Create a new video record"""
        pass

    @abstractmethod
    async def get_by_id(self, video_id: int) -> Optional[Video]:
        """Get video by ID"""
        pass

    @abstractmethod
    async def get_all(self) -> List[Video]:
        """Get all videos"""
        pass

    @abstractmethod
    async def get_by_status(self, status: VideoStatus) -> List[Video]:
        """Get videos by status"""
        pass

    @abstractmethod
    async def update(self, video: Video) -> Video:
        """Update video information"""
        pass

    @abstractmethod
    async def update_status(self, video_id: int, status: VideoStatus) -> bool:
        """Update video status"""
        pass

    @abstractmethod
    async def delete(self, video_id: int) -> bool:
        """Delete video record"""
        pass

    @abstractmethod
    async def exists_by_filename(self, filename: str) -> bool:
        """Check if a video with the given filename already exists"""
        pass