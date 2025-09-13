from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.exc import SQLAlchemyError
import logging

from domain.entities.translation import (
    Translation,
    TranslationJob,
    TranslationStatus,
    TranslationSegment,
    VideoSceneContext,
    CulturalAdaptation
)
from domain.repositories.translation_repository import TranslationRepository, TranslationJobRepository
from infrastructure.database.models import TranslationModel, TranslationJobModel, TranslationStatusEnum

logger = logging.getLogger(__name__)


class TranslationRepositoryImpl(TranslationRepository):
    """SQLAlchemy implementation of TranslationRepository"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create(self, translation: Translation) -> Translation:
        """Create a new translation"""
        db_translation = TranslationModel(
            video_id=translation.video_id,
            transcription_id=translation.transcription_id,
            country_id=translation.country_id,
            source_language=translation.source_language,
            target_language=translation.target_language,
            country_code=translation.country_code,
            status=translation.status,
            progress_percentage=translation.progress_percentage,
            segments=self._segments_to_json(translation.segments) if translation.segments else None,
            full_translated_text=translation.full_translated_text,
            video_analysis=translation.video_analysis,
            advertising_context=translation.advertising_context,
            cultural_adaptation=translation.cultural_adaptation.dict() if translation.cultural_adaptation else None,
            overall_confidence=translation.overall_confidence,
            cultural_appropriateness_score=translation.cultural_appropriateness_score,
            brand_consistency_score=translation.brand_consistency_score,
            effectiveness_prediction=translation.effectiveness_prediction,
            model_used=translation.model_used,
            processing_time=translation.processing_time,
            tokens_used=translation.tokens_used,
            error_message=translation.error_message,
            warnings=translation.warnings
        )

        self.db.add(db_translation)
        await self.db.commit()
        await self.db.refresh(db_translation)

        return self._to_entity(db_translation)

    async def get_by_id(self, translation_id: int) -> Optional[Translation]:
        """Get translation by ID"""
        try:
            result = await self.db.execute(
                select(TranslationModel).where(TranslationModel.id == translation_id)
            )
            db_translation = result.scalar_one_or_none()
            return self._to_entity(db_translation) if db_translation else None
        except SQLAlchemyError as e:
            logger.error(f"Error getting translation by ID {translation_id}: {str(e)}")
            raise

    async def get_by_video_id(self, video_id: int) -> List[Translation]:
        """Get all translations for a video"""
        try:
            result = await self.db.execute(
                select(TranslationModel).where(TranslationModel.video_id == video_id)
            )
            db_translations = result.scalars().all()
            return [self._to_entity(db_translation) for db_translation in db_translations]
        except SQLAlchemyError as e:
            logger.error(f"Error getting translations for video {video_id}: {str(e)}")
            raise

    async def get_by_video_and_country(self, video_id: int, country_id: int) -> Optional[Translation]:
        """Get translation for specific video and country combination"""
        try:
            result = await self.db.execute(
                select(TranslationModel).where(
                    and_(
                        TranslationModel.video_id == video_id,
                        TranslationModel.country_id == country_id
                    )
                )
            )
            db_translation = result.scalar_one_or_none()
            return self._to_entity(db_translation) if db_translation else None
        except SQLAlchemyError as e:
            logger.error(f"Error getting translation for video {video_id} and country {country_id}: {str(e)}")
            raise

    async def get_by_country_id(self, country_id: int) -> List[Translation]:
        """Get all translations for a country"""
        db_translations = self.db.query(TranslationModel).filter(
            TranslationModel.country_id == country_id
        ).all()
        return [self._to_entity(db_translation) for db_translation in db_translations]

    async def get_by_status(self, status: TranslationStatus) -> List[Translation]:
        """Get translations by status"""
        db_translations = self.db.query(TranslationModel).filter(
            TranslationModel.status == status
        ).all()
        return [self._to_entity(db_translation) for db_translation in db_translations]

    async def get_by_transcription_id(self, transcription_id: int) -> List[Translation]:
        """Get translations by transcription ID"""
        db_translations = self.db.query(TranslationModel).filter(
            TranslationModel.transcription_id == transcription_id
        ).all()
        return [self._to_entity(db_translation) for db_translation in db_translations]

    async def update(self, translation: Translation) -> Translation:
        """Update existing translation"""
        result = await self.db.execute(
            select(TranslationModel).where(TranslationModel.id == translation.id)
        )
        db_translation = result.scalar_one_or_none()
        if not db_translation:
            raise ValueError(f"Translation with ID {translation.id} not found")

        # Update fields
        db_translation.status = translation.status
        db_translation.progress_percentage = translation.progress_percentage
        db_translation.segments = self._segments_to_json(translation.segments) if translation.segments else None
        db_translation.full_translated_text = translation.full_translated_text
        db_translation.video_analysis = translation.video_analysis
        db_translation.advertising_context = translation.advertising_context
        db_translation.cultural_adaptation = translation.cultural_adaptation.dict() if translation.cultural_adaptation else None
        db_translation.overall_confidence = translation.overall_confidence
        db_translation.cultural_appropriateness_score = translation.cultural_appropriateness_score
        db_translation.brand_consistency_score = translation.brand_consistency_score
        db_translation.effectiveness_prediction = translation.effectiveness_prediction
        db_translation.processing_time = translation.processing_time
        db_translation.tokens_used = translation.tokens_used
        db_translation.error_message = translation.error_message
        db_translation.warnings = translation.warnings

        await self.db.commit()
        await self.db.refresh(db_translation)

        return self._to_entity(db_translation)

    async def update_status(self, translation_id: int, status: TranslationStatus) -> bool:
        """Update translation status"""
        db_translation = self.db.query(TranslationModel).filter(
            TranslationModel.id == translation_id
        ).first()
        if not db_translation:
            return False

        db_translation.status = status
        self.db.commit()
        return True

    async def delete(self, translation_id: int) -> bool:
        """Delete translation by ID"""
        db_translation = self.db.query(TranslationModel).filter(
            TranslationModel.id == translation_id
        ).first()
        if not db_translation:
            return False

        self.db.delete(db_translation)
        self.db.commit()
        return True

    async def get_completed_translations(self, limit: Optional[int] = None) -> List[Translation]:
        """Get completed translations"""
        query = self.db.query(TranslationModel).filter(
            TranslationModel.status == TranslationStatusEnum.COMPLETED
        ).order_by(TranslationModel.updated_at.desc())

        if limit:
            query = query.limit(limit)

        db_translations = query.all()
        return [self._to_entity(db_translation) for db_translation in db_translations]

    async def get_failed_translations(self, limit: Optional[int] = None) -> List[Translation]:
        """Get failed translations"""
        query = self.db.query(TranslationModel).filter(
            TranslationModel.status == TranslationStatusEnum.FAILED
        ).order_by(TranslationModel.updated_at.desc())

        if limit:
            query = query.limit(limit)

        db_translations = query.all()
        return [self._to_entity(db_translation) for db_translation in db_translations]

    def _segments_to_json(self, segments: List[TranslationSegment]) -> List[dict]:
        """Convert segments to JSON-serializable format"""
        return [
            {
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "original_text": seg.original_text,
                "translated_text": seg.translated_text,
                "confidence_score": seg.confidence_score,
                "context_used": seg.context_used,
                "cultural_adaptations": seg.cultural_adaptations,
                "scene_context": seg.scene_context.dict() if seg.scene_context else None
            }
            for seg in segments
        ]

    def _json_to_segments(self, segments_json: List[dict]) -> List[TranslationSegment]:
        """Convert JSON to TranslationSegment objects"""
        segments = []
        for seg_data in segments_json:
            scene_context = None
            if seg_data.get("scene_context"):
                scene_context = VideoSceneContext(**seg_data["scene_context"])

            segment = TranslationSegment(
                start_time=seg_data.get("start_time", 0),
                end_time=seg_data.get("end_time", 0),
                original_text=seg_data.get("original_text", ""),
                translated_text=seg_data.get("translated_text", ""),
                confidence_score=seg_data.get("confidence_score", 0.0),
                context_used=seg_data.get("context_used", []),
                cultural_adaptations=seg_data.get("cultural_adaptations", []),
                scene_context=scene_context
            )
            segments.append(segment)
        return segments

    def _to_entity(self, db_translation: TranslationModel) -> Translation:
        """Convert database model to domain entity"""
        if not db_translation:
            return None

        # Parse segments
        segments = []
        if db_translation.segments:
            segments = self._json_to_segments(db_translation.segments)

        # Parse cultural adaptation
        cultural_adaptation = None
        if db_translation.cultural_adaptation:
            cultural_adaptation = CulturalAdaptation(**db_translation.cultural_adaptation)

        return Translation(
            id=db_translation.id,
            video_id=db_translation.video_id,
            transcription_id=db_translation.transcription_id,
            country_id=db_translation.country_id,
            source_language=db_translation.source_language,
            target_language=db_translation.target_language,
            country_code=db_translation.country_code,
            status=db_translation.status,
            progress_percentage=db_translation.progress_percentage,
            segments=segments,
            full_translated_text=db_translation.full_translated_text,
            video_analysis=db_translation.video_analysis or {},
            advertising_context=db_translation.advertising_context or {},
            cultural_adaptation=cultural_adaptation,
            overall_confidence=db_translation.overall_confidence,
            cultural_appropriateness_score=db_translation.cultural_appropriateness_score,
            brand_consistency_score=db_translation.brand_consistency_score,
            effectiveness_prediction=db_translation.effectiveness_prediction,
            model_used=db_translation.model_used,
            processing_time=db_translation.processing_time,
            tokens_used=db_translation.tokens_used,
            error_message=db_translation.error_message,
            warnings=db_translation.warnings or [],
            created_at=db_translation.created_at,
            updated_at=db_translation.updated_at
        )


class TranslationJobRepositoryImpl(TranslationJobRepository):
    """SQLAlchemy implementation of TranslationJobRepository"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create(self, job: TranslationJob) -> TranslationJob:
        """Create a new translation job"""
        db_job = TranslationJobModel(
            video_id=job.video_id,
            user_id=job.user_id,
            target_countries=job.target_countries,
            preserve_brand_elements=job.preserve_brand_elements,
            adapt_for_culture=job.adapt_for_culture,
            maintain_video_timing=job.maintain_video_timing,
            analysis_depth=job.analysis_depth,
            cultural_sensitivity=job.cultural_sensitivity,
            brand_consistency=job.brand_consistency,
            status=job.status,
            progress_percentage=job.progress_percentage,
            translations=job.translations,
            success_count=job.success_count,
            failure_count=job.failure_count
        )

        self.db.add(db_job)
        self.db.commit()
        self.db.refresh(db_job)

        return self._job_to_entity(db_job)

    async def get_by_id(self, job_id: int) -> Optional[TranslationJob]:
        """Get translation job by ID"""
        db_job = self.db.query(TranslationJobModel).filter(
            TranslationJobModel.id == job_id
        ).first()
        return self._job_to_entity(db_job) if db_job else None

    async def get_by_video_id(self, video_id: int) -> List[TranslationJob]:
        """Get translation jobs for a video"""
        db_jobs = self.db.query(TranslationJobModel).filter(
            TranslationJobModel.video_id == video_id
        ).all()
        return [self._job_to_entity(db_job) for db_job in db_jobs]

    async def get_by_user_id(self, user_id: int) -> List[TranslationJob]:
        """Get translation jobs for a user"""
        db_jobs = self.db.query(TranslationJobModel).filter(
            TranslationJobModel.user_id == user_id
        ).all()
        return [self._job_to_entity(db_job) for db_job in db_jobs]

    async def get_by_status(self, status: str) -> List[TranslationJob]:
        """Get translation jobs by status"""
        db_jobs = self.db.query(TranslationJobModel).filter(
            TranslationJobModel.status == status
        ).all()
        return [self._job_to_entity(db_job) for db_job in db_jobs]

    async def update(self, job: TranslationJob) -> TranslationJob:
        """Update existing translation job"""
        db_job = self.db.query(TranslationJobModel).filter(
            TranslationJobModel.id == job.id
        ).first()
        if not db_job:
            raise ValueError(f"Translation job with ID {job.id} not found")

        # Update fields
        db_job.status = job.status
        db_job.progress_percentage = job.progress_percentage
        db_job.translations = job.translations
        db_job.total_processing_time = job.total_processing_time
        db_job.success_count = job.success_count
        db_job.failure_count = job.failure_count

        self.db.commit()
        self.db.refresh(db_job)

        return self._job_to_entity(db_job)

    async def delete(self, job_id: int) -> bool:
        """Delete translation job by ID"""
        db_job = self.db.query(TranslationJobModel).filter(
            TranslationJobModel.id == job_id
        ).first()
        if not db_job:
            return False

        self.db.delete(db_job)
        self.db.commit()
        return True

    async def get_active_jobs(self) -> List[TranslationJob]:
        """Get all active translation jobs"""
        db_jobs = self.db.query(TranslationJobModel).filter(
            TranslationJobModel.status.in_(["created", "processing"])
        ).all()
        return [self._job_to_entity(db_job) for db_job in db_jobs]

    def _job_to_entity(self, db_job: TranslationJobModel) -> TranslationJob:
        """Convert database model to domain entity"""
        if not db_job:
            return None

        return TranslationJob(
            id=db_job.id,
            video_id=db_job.video_id,
            user_id=db_job.user_id,
            target_countries=db_job.target_countries or [],
            preserve_brand_elements=db_job.preserve_brand_elements,
            adapt_for_culture=db_job.adapt_for_culture,
            maintain_video_timing=db_job.maintain_video_timing,
            analysis_depth=db_job.analysis_depth,
            cultural_sensitivity=db_job.cultural_sensitivity,
            brand_consistency=db_job.brand_consistency,
            status=db_job.status,
            progress_percentage=db_job.progress_percentage,
            translations=db_job.translations or [],
            total_processing_time=db_job.total_processing_time,
            success_count=db_job.success_count,
            failure_count=db_job.failure_count,
            created_at=db_job.created_at,
            updated_at=db_job.updated_at
        )
