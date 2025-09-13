from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import SQLAlchemyError
import logging

from domain.repositories.video_repository import VideoRepository
from domain.entities.video import Video, VideoStatus
from infrastructure.database.models import VideoModel

logger = logging.getLogger(__name__)


class VideoRepositoryImpl(VideoRepository):
    """SQLAlchemy implementation of VideoRepository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, video: Video) -> Video:
        """Create a new video record"""
        try:
            # Convert domain entity to database model
            video_model = VideoModel(
                filename=video.filename,
                original_filename=video.original_filename,
                file_path=video.file_path,
                file_size=video.file_size,
                duration=video.duration,
                status=video.status.value if isinstance(video.status, VideoStatus) else video.status,
                content_type=video.content_type,
                language=video.language,
                description=video.description,
                is_advertisement=video.is_advertisement
            )

            self.session.add(video_model)
            await self.session.commit()
            await self.session.refresh(video_model)

            # Convert back to domain entity
            return self._model_to_entity(video_model)

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error creating video: {str(e)}")
            raise

    async def get_by_id(self, video_id: int) -> Optional[Video]:
        """Get video by ID"""
        try:
            result = await self.session.execute(
                select(VideoModel).where(VideoModel.id == video_id)
            )
            video_model = result.scalar_one_or_none()

            if video_model:
                return self._model_to_entity(video_model)
            return None

        except SQLAlchemyError as e:
            logger.error(f"Error getting video by ID {video_id}: {str(e)}")
            raise

    async def get_all(self) -> List[Video]:
        """Get all videos"""
        try:
            result = await self.session.execute(select(VideoModel))
            video_models = result.scalars().all()

            return [self._model_to_entity(model) for model in video_models]

        except SQLAlchemyError as e:
            logger.error(f"Error getting all videos: {str(e)}")
            raise

    async def get_by_status(self, status: VideoStatus) -> List[Video]:
        """Get videos by status"""
        try:
            status_value = status.value if isinstance(status, VideoStatus) else status
            result = await self.session.execute(
                select(VideoModel).where(VideoModel.status == status_value)
            )
            video_models = result.scalars().all()

            return [self._model_to_entity(model) for model in video_models]

        except SQLAlchemyError as e:
            logger.error(f"Error getting videos by status {status}: {str(e)}")
            raise

    async def update(self, video: Video) -> Video:
        """Update video information"""
        try:
            # Update the model
            await self.session.execute(
                update(VideoModel)
                .where(VideoModel.id == video.id)
                .values(
                    filename=video.filename,
                    original_filename=video.original_filename,
                    file_path=video.file_path,
                    file_size=video.file_size,
                    duration=video.duration,
                    status=video.status.value if isinstance(video.status, VideoStatus) else video.status,
                    content_type=video.content_type,
                    language=video.language,
                    description=video.description,
                    is_advertisement=video.is_advertisement
                )
            )

            await self.session.commit()

            # Fetch and return updated video
            return await self.get_by_id(video.id)

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating video {video.id}: {str(e)}")
            raise

    async def update_status(self, video_id: int, status: VideoStatus) -> bool:
        """Update video status"""
        try:
            status_value = status.value if isinstance(status, VideoStatus) else status
            result = await self.session.execute(
                update(VideoModel)
                .where(VideoModel.id == video_id)
                .values(status=status_value)
            )

            await self.session.commit()
            return result.rowcount > 0

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating video status {video_id}: {str(e)}")
            raise

    async def delete(self, video_id: int) -> bool:
        """Delete video record"""
        try:
            result = await self.session.execute(
                delete(VideoModel).where(VideoModel.id == video_id)
            )

            await self.session.commit()
            return result.rowcount > 0

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error deleting video {video_id}: {str(e)}")
            raise

    async def exists_by_filename(self, filename: str) -> bool:
        """Check if a video with the given filename already exists"""
        try:
            result = await self.session.execute(
                select(VideoModel).where(VideoModel.filename == filename)
            )
            return result.scalar_one_or_none() is not None

        except SQLAlchemyError as e:
            logger.error(f"Error checking video existence by filename {filename}: {str(e)}")
            raise

    def _model_to_entity(self, model: VideoModel) -> Video:
        """Convert database model to domain entity"""
        return Video(
            id=model.id,
            filename=model.filename,
            original_filename=model.original_filename,
            file_path=model.file_path,
            file_size=model.file_size,
            duration=model.duration,
            status=model.status,
            content_type=model.content_type,
            language=model.language,
            description=model.description,
            is_advertisement=model.is_advertisement,
            created_at=model.created_at,
            updated_at=model.updated_at
        )