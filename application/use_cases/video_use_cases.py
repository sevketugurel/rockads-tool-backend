import os
import uuid
import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from domain.entities.video import Video, VideoStatus
from domain.entities.transcription import Transcription, TranscriptionStatus
from domain.repositories.video_repository import VideoRepository
from domain.repositories.transcription_repository import TranscriptionRepository
from application.services.ai.transcription_service import TranscriptionService
from core.config.settings import settings

logger = logging.getLogger(__name__)


class VideoUseCases:
    """Business logic for video operations"""

    def __init__(
        self,
        video_repository: VideoRepository,
        transcription_repository: TranscriptionRepository,
        transcription_service: TranscriptionService
    ):
        self.video_repository = video_repository
        self.transcription_repository = transcription_repository
        self.transcription_service = transcription_service

    def _get_video_duration(self, file_path: str) -> Optional[float]:
        """Extract video duration using moviepy (runs in thread pool)"""
        try:
            from moviepy.editor import VideoFileClip
            with VideoFileClip(file_path) as video_clip:
                return video_clip.duration
        except Exception as e:
            logger.warning(f"Could not extract duration from {file_path}: {str(e)}")
            return None

    async def upload_video(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        description: Optional[str] = None
    ) -> Video:
        """
        Handle video upload with validation and storage

        Args:
            file_content: Binary content of the video file
            filename: Original filename
            content_type: MIME type of the file
            description: Optional description

        Returns:
            Created Video entity

        Raises:
            ValueError: If validation fails
        """
        # Validate file type
        if content_type not in settings.allowed_video_types:
            raise ValueError(f"Unsupported file type: {content_type}")

        # Validate file size
        if len(file_content) > settings.max_file_size:
            raise ValueError(f"File too large. Maximum size: {settings.max_file_size} bytes")

        # Generate unique filename
        file_extension = Path(filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"

        # Ensure upload directory exists
        upload_path = Path(settings.upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = upload_path / unique_filename
        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info(f"Video file saved: {file_path}")

        # Extract video duration asynchronously to avoid blocking upload
        duration = None
        try:
            # Use asyncio to run moviepy in executor to prevent blocking
            loop = asyncio.get_event_loop()
            duration = await loop.run_in_executor(
                None,
                self._get_video_duration,
                str(file_path)
            )
        except Exception as e:
            logger.warning(f"Could not extract video duration: {str(e)}")
            duration = None

        # Create video entity
        video = Video(
            filename=unique_filename,
            original_filename=filename,
            file_path=str(file_path),
            file_size=len(file_content),
            duration=duration,
            status=VideoStatus.UPLOADED,
            content_type=content_type,
            description=description,
            is_advertisement=True  # Defaulting to advertisement context
        )

        # Save to database
        return await self.video_repository.create(video)

    async def get_video_by_id(self, video_id: int) -> Optional[Video]:
        """Get video by ID"""
        return await self.video_repository.get_by_id(video_id)

    async def get_all_videos(self) -> List[Video]:
        """Get all videos"""
        return await self.video_repository.get_all()

    async def get_videos_by_status(self, status: VideoStatus) -> List[Video]:
        """Get videos by status"""
        return await self.video_repository.get_by_status(status)

    async def transcribe_video(
        self,
        video_id: int,
        language_hint: Optional[str] = None
    ) -> Transcription:
        """
        Transcribe video using AI service

        Args:
            video_id: ID of the video to transcribe
            language_hint: Optional language hint for better accuracy

        Returns:
            Transcription entity

        Raises:
            ValueError: If video not found or already transcribed
        """
        # Get video
        video = await self.video_repository.get_by_id(video_id)
        if not video:
            raise ValueError("Video not found")

        # Check if already transcribed
        existing_transcription = await self.transcription_repository.get_by_video_id(video_id)
        if existing_transcription and existing_transcription.status == TranscriptionStatus.COMPLETED:
            logger.info(f"Video {video_id} already transcribed")
            return existing_transcription

        # Update video status to processing
        await self.video_repository.update_status(video_id, VideoStatus.PROCESSING)

        try:
            logger.info(f"Starting transcription for video {video_id}")

            # Create initial transcription record
            transcription = Transcription(
                video_id=video_id,
                status=TranscriptionStatus.PROCESSING,
                language_code=language_hint or "auto"
            )
            transcription = await self.transcription_repository.create(transcription)

            # Perform transcription using AI service
            ai_transcription = await self.transcription_service.transcribe_video(
                video.file_path,
                language_hint
            )

            # Update transcription with results
            ai_transcription.id = transcription.id
            ai_transcription.video_id = video_id
            transcription = await self.transcription_repository.update(ai_transcription)

            # Update video status and detected language
            if transcription.status == TranscriptionStatus.COMPLETED:
                await self.video_repository.update_status(video_id, VideoStatus.TRANSCRIBED)

                # Update video with detected language
                video.language = transcription.language_code
                video.status = VideoStatus.TRANSCRIBED
                await self.video_repository.update(video)
            else:
                await self.video_repository.update_status(video_id, VideoStatus.FAILED)

            logger.info(f"Transcription completed for video {video_id}")
            return transcription

        except Exception as e:
            logger.error(f"Transcription failed for video {video_id}: {str(e)}")

            # Update statuses to failed
            await self.video_repository.update_status(video_id, VideoStatus.FAILED)

            if 'transcription' in locals():
                transcription.status = TranscriptionStatus.FAILED
                transcription.error_message = str(e)
                await self.transcription_repository.update(transcription)

            raise

    async def get_video_transcription(self, video_id: int) -> Optional[Transcription]:
        """Get transcription for a video"""
        return await self.transcription_repository.get_by_video_id(video_id)

    async def delete_video(self, video_id: int) -> bool:
        """
        Delete video and associated files

        Args:
            video_id: ID of the video to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        # Get video
        video = await self.video_repository.get_by_id(video_id)
        if not video:
            return False

        try:
            # Delete physical file
            file_path = Path(video.file_path)
            if file_path.exists():
                file_path.unlink()

            # Delete from database (cascade will delete related records)
            success = await self.video_repository.delete(video_id)

            logger.info(f"Video {video_id} deleted successfully")
            return success

        except Exception as e:
            logger.error(f"Error deleting video {video_id}: {str(e)}")
            raise

    async def get_video_processing_status(self, video_id: int) -> dict:
        """
        Get processing status for a video including transcription status

        Args:
            video_id: ID of the video

        Returns:
            Dictionary with status information
        """
        video = await self.video_repository.get_by_id(video_id)
        if not video:
            raise ValueError("Video not found")

        transcription = await self.transcription_repository.get_by_video_id(video_id)

        return {
            "video_id": video_id,
            "video_status": video.status,
            "transcription_status": transcription.status if transcription else None,
            "language": video.language,
            "duration": video.duration,
            "created_at": video.created_at,
            "updated_at": video.updated_at,
            "transcription_confidence": transcription.confidence_score if transcription else None,
            "processing_time": transcription.processing_time if transcription else None
        }