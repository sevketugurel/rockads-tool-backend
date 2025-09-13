from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import SQLAlchemyError
import logging

from domain.entities.localization_job import LocalizationJob, LocalizationJobStatus, TargetLanguage
from domain.repositories.localization_job_repository import LocalizationJobRepository
from infrastructure.database.models import LocalizationJobModel, LocalizationJobStatusEnum

logger = logging.getLogger(__name__)


class LocalizationJobRepositoryImpl(LocalizationJobRepository):
    """SQLAlchemy implementation of LocalizationJobRepository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: LocalizationJob) -> LocalizationJob:
        """Create a new localization job"""
        try:
            db_job = LocalizationJobModel(
                video_id=job.video_id,
                user_id=job.user_id,
                status=job.status,
                source_language=job.source_language,
                target_languages=[lang.dict() for lang in job.target_languages] if job.target_languages else [],
                target_countries=job.target_countries or [],
                transcription_id=job.transcription_id,
                translation_ids=job.translation_ids,
                audio_generation_ids=job.audio_generation_ids,
                output_video_ids=job.output_video_ids,
                preserve_timing=job.preserve_timing,
                adjust_for_culture=job.adjust_for_culture,
                voice_tone=job.voice_tone,
                progress_percentage=job.progress_percentage,
                estimated_completion=job.estimated_completion,
                total_processing_time=job.total_processing_time,
                error_details=job.error_details
            )

            self.session.add(db_job)
            await self.session.commit()
            await self.session.refresh(db_job)

            return self._to_entity(db_job)
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error creating localization job: {str(e)}")
            raise

    async def get_by_id(self, job_id: int) -> Optional[LocalizationJob]:
        """Get localization job by ID"""
        try:
            result = await self.session.execute(
                select(LocalizationJobModel).where(LocalizationJobModel.id == job_id)
            )
            db_job = result.scalar_one_or_none()
            return self._to_entity(db_job) if db_job else None
        except SQLAlchemyError as e:
            logger.error(f"Error getting localization job by ID {job_id}: {str(e)}")
            raise

    async def get_by_video_id(self, video_id: int) -> List[LocalizationJob]:
        """Get localization jobs for a video"""
        try:
            result = await self.session.execute(
                select(LocalizationJobModel).where(LocalizationJobModel.video_id == video_id)
            )
            db_jobs = result.scalars().all()
            return [self._to_entity(db_job) for db_job in db_jobs]
        except SQLAlchemyError as e:
            logger.error(f"Error getting localization jobs for video {video_id}: {str(e)}")
            raise

    async def get_by_user_id(self, user_id: int) -> List[LocalizationJob]:
        """Get localization jobs for a user"""
        try:
            result = await self.session.execute(
                select(LocalizationJobModel).where(LocalizationJobModel.user_id == user_id)
            )
            db_jobs = result.scalars().all()
            return [self._to_entity(db_job) for db_job in db_jobs]
        except SQLAlchemyError as e:
            logger.error(f"Error getting localization jobs for user {user_id}: {str(e)}")
            raise

    async def get_by_status(self, status: LocalizationJobStatus) -> List[LocalizationJob]:
        """Get localization jobs by status"""
        try:
            result = await self.session.execute(
                select(LocalizationJobModel).where(LocalizationJobModel.status == status)
            )
            db_jobs = result.scalars().all()
            return [self._to_entity(db_job) for db_job in db_jobs]
        except SQLAlchemyError as e:
            logger.error(f"Error getting localization jobs by status {status}: {str(e)}")
            raise

    async def get_all(self) -> List[LocalizationJob]:
        """Get all localization jobs"""
        try:
            result = await self.session.execute(select(LocalizationJobModel))
            db_jobs = result.scalars().all()
            return [self._to_entity(db_job) for db_job in db_jobs]
        except SQLAlchemyError as e:
            logger.error(f"Error getting all localization jobs: {str(e)}")
            raise

    async def update(self, job: LocalizationJob) -> LocalizationJob:
        """Update existing localization job"""
        try:
            result = await self.session.execute(
                select(LocalizationJobModel).where(LocalizationJobModel.id == job.id)
            )
            db_job = result.scalar_one_or_none()
            if not db_job:
                raise ValueError(f"Localization job with ID {job.id} not found")

            # Update fields
            db_job.status = job.status
            db_job.transcription_id = job.transcription_id
            db_job.translation_ids = job.translation_ids
            db_job.audio_generation_ids = job.audio_generation_ids
            db_job.output_video_ids = job.output_video_ids
            db_job.progress_percentage = job.progress_percentage
            db_job.estimated_completion = job.estimated_completion
            db_job.total_processing_time = job.total_processing_time
            db_job.error_details = job.error_details
            db_job.target_countries = job.target_countries

            await self.session.commit()
            await self.session.refresh(db_job)

            return self._to_entity(db_job)
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating localization job {job.id}: {str(e)}")
            raise

    async def update_status(self, job_id: int, status: LocalizationJobStatus) -> bool:
        """Update job status"""
        try:
            result = await self.session.execute(
                update(LocalizationJobModel)
                .where(LocalizationJobModel.id == job_id)
                .values(status=status)
            )
            await self.session.commit()
            return result.rowcount > 0
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating job status for job {job_id}: {str(e)}")
            raise

    async def update_progress(self, job_id: int, progress: float) -> bool:
        """Update job progress percentage"""
        try:
            result = await self.session.execute(
                update(LocalizationJobModel)
                .where(LocalizationJobModel.id == job_id)
                .values(progress_percentage=progress)
            )
            await self.session.commit()
            return result.rowcount > 0
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating job progress for job {job_id}: {str(e)}")
            raise

    async def delete(self, job_id: int) -> bool:
        """Delete localization job by ID"""
        try:
            result = await self.session.execute(
                delete(LocalizationJobModel).where(LocalizationJobModel.id == job_id)
            )
            await self.session.commit()
            return result.rowcount > 0
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error deleting localization job {job_id}: {str(e)}")
            raise

    async def get_active_jobs(self) -> List[LocalizationJob]:
        """Get all active localization jobs"""
        try:
            active_statuses = [
                LocalizationJobStatusEnum.CREATED,
                LocalizationJobStatusEnum.TRANSCRIBING,
                LocalizationJobStatusEnum.TRANSLATING,
                LocalizationJobStatusEnum.GENERATING_SPEECH,
                LocalizationJobStatusEnum.PROCESSING_VIDEO
            ]

            result = await self.session.execute(
                select(LocalizationJobModel).where(LocalizationJobModel.status.in_(active_statuses))
            )
            db_jobs = result.scalars().all()
            return [self._to_entity(db_job) for db_job in db_jobs]
        except SQLAlchemyError as e:
            logger.error(f"Error getting active localization jobs: {str(e)}")
            raise

    async def get_pending_jobs(self, limit: Optional[int] = None) -> List[LocalizationJob]:
        """Get pending localization jobs"""
        try:
            query = select(LocalizationJobModel).where(
                LocalizationJobModel.status == LocalizationJobStatusEnum.CREATED
            ).order_by(LocalizationJobModel.created_at)

            if limit:
                query = query.limit(limit)

            result = await self.session.execute(query)
            db_jobs = result.scalars().all()
            return [self._to_entity(db_job) for db_job in db_jobs]
        except SQLAlchemyError as e:
            logger.error(f"Error getting pending localization jobs: {str(e)}")
            raise

    def _to_entity(self, db_job: LocalizationJobModel) -> LocalizationJob:
        """Convert database model to domain entity"""
        if not db_job:
            return None

        # Parse target languages
        target_languages = []
        if db_job.target_languages:
            target_languages = [
                TargetLanguage(**lang_data) for lang_data in db_job.target_languages
            ]

        return LocalizationJob(
            id=db_job.id,
            video_id=db_job.video_id,
            user_id=db_job.user_id,
            status=db_job.status,
            source_language=db_job.source_language,
            target_languages=target_languages,
            target_countries=db_job.target_countries or [],
            transcription_id=db_job.transcription_id,
            translation_ids=db_job.translation_ids or [],
            audio_generation_ids=db_job.audio_generation_ids or [],
            output_video_ids=db_job.output_video_ids or [],
            preserve_timing=db_job.preserve_timing,
            adjust_for_culture=db_job.adjust_for_culture,
            voice_tone=db_job.voice_tone,
            progress_percentage=db_job.progress_percentage,
            estimated_completion=db_job.estimated_completion,
            total_processing_time=db_job.total_processing_time,
            error_details=db_job.error_details or [],
            created_at=db_job.created_at,
            updated_at=db_job.updated_at
        )
