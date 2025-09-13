from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import SQLAlchemyError
import logging
import json

from domain.repositories.transcription_repository import TranscriptionRepository
from domain.entities.transcription import Transcription, TranscriptionStatus, TranscriptionSegment
from infrastructure.database.models import TranscriptionModel

logger = logging.getLogger(__name__)


class TranscriptionRepositoryImpl(TranscriptionRepository):
    """SQLAlchemy implementation of TranscriptionRepository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, transcription: Transcription) -> Transcription:
        """Create a new transcription record"""
        try:
            # Convert segments to JSON
            segments_json = None
            if transcription.segments:
                segments_json = [
                    {
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "text": seg.text,
                        "confidence": seg.confidence,
                        "speaker_id": seg.speaker_id
                    }
                    for seg in transcription.segments
                ]

            # Convert domain entity to database model
            transcription_model = TranscriptionModel(
                video_id=transcription.video_id,
                status=transcription.status.value if isinstance(transcription.status, TranscriptionStatus) else transcription.status,
                language_code=transcription.language_code,
                full_text=transcription.full_text,
                segments=segments_json,
                confidence_score=transcription.confidence_score,
                processing_time=transcription.processing_time,
                model_used=transcription.model_used,
                extra_metadata=transcription.extra_metadata,
                error_message=transcription.error_message
            )

            self.session.add(transcription_model)
            await self.session.commit()
            await self.session.refresh(transcription_model)

            # Convert back to domain entity
            return self._model_to_entity(transcription_model)

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error creating transcription: {str(e)}")
            raise

    async def get_by_id(self, transcription_id: int) -> Optional[Transcription]:
        """Get transcription by ID"""
        try:
            result = await self.session.execute(
                select(TranscriptionModel).where(TranscriptionModel.id == transcription_id)
            )
            transcription_model = result.scalar_one_or_none()

            if transcription_model:
                return self._model_to_entity(transcription_model)
            return None

        except SQLAlchemyError as e:
            logger.error(f"Error getting transcription by ID {transcription_id}: {str(e)}")
            raise

    async def get_by_video_id(self, video_id: int) -> Optional[Transcription]:
        """Get transcription by video ID"""
        try:
            result = await self.session.execute(
                select(TranscriptionModel).where(TranscriptionModel.video_id == video_id)
            )
            transcription_model = result.scalar_one_or_none()

            if transcription_model:
                return self._model_to_entity(transcription_model)
            return None

        except SQLAlchemyError as e:
            logger.error(f"Error getting transcription by video ID {video_id}: {str(e)}")
            raise

    async def get_all(self) -> List[Transcription]:
        """Get all transcriptions"""
        try:
            result = await self.session.execute(select(TranscriptionModel))
            transcription_models = result.scalars().all()

            return [self._model_to_entity(model) for model in transcription_models]

        except SQLAlchemyError as e:
            logger.error(f"Error getting all transcriptions: {str(e)}")
            raise

    async def get_by_status(self, status: TranscriptionStatus) -> List[Transcription]:
        """Get transcriptions by status"""
        try:
            status_value = status.value if isinstance(status, TranscriptionStatus) else status
            result = await self.session.execute(
                select(TranscriptionModel).where(TranscriptionModel.status == status_value)
            )
            transcription_models = result.scalars().all()

            return [self._model_to_entity(model) for model in transcription_models]

        except SQLAlchemyError as e:
            logger.error(f"Error getting transcriptions by status {status}: {str(e)}")
            raise

    async def update(self, transcription: Transcription) -> Transcription:
        """Update transcription"""
        try:
            # Convert segments to JSON
            segments_json = None
            if transcription.segments:
                segments_json = [
                    {
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "text": seg.text,
                        "confidence": seg.confidence,
                        "speaker_id": seg.speaker_id
                    }
                    for seg in transcription.segments
                ]

            # Update the model
            await self.session.execute(
                update(TranscriptionModel)
                .where(TranscriptionModel.id == transcription.id)
                .values(
                    video_id=transcription.video_id,
                    status=transcription.status.value if isinstance(transcription.status, TranscriptionStatus) else transcription.status,
                    language_code=transcription.language_code,
                    full_text=transcription.full_text,
                    segments=segments_json,
                    confidence_score=transcription.confidence_score,
                    processing_time=transcription.processing_time,
                    model_used=transcription.model_used,
                    extra_metadata=transcription.extra_metadata,
                    error_message=transcription.error_message
                )
            )

            await self.session.commit()

            # Fetch and return updated transcription
            return await self.get_by_id(transcription.id)

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating transcription {transcription.id}: {str(e)}")
            raise

    async def update_status(self, transcription_id: int, status: TranscriptionStatus) -> bool:
        """Update transcription status"""
        try:
            status_value = status.value if isinstance(status, TranscriptionStatus) else status
            result = await self.session.execute(
                update(TranscriptionModel)
                .where(TranscriptionModel.id == transcription_id)
                .values(status=status_value)
            )

            await self.session.commit()
            return result.rowcount > 0

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating transcription status {transcription_id}: {str(e)}")
            raise

    async def delete(self, transcription_id: int) -> bool:
        """Delete transcription"""
        try:
            result = await self.session.execute(
                delete(TranscriptionModel).where(TranscriptionModel.id == transcription_id)
            )

            await self.session.commit()
            return result.rowcount > 0

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error deleting transcription {transcription_id}: {str(e)}")
            raise

    def _model_to_entity(self, model: TranscriptionModel) -> Transcription:
        """Convert database model to domain entity"""
        # Convert segments from JSON
        segments = []
        if model.segments:
            for seg_data in model.segments:
                segments.append(TranscriptionSegment(
                    start_time=seg_data.get("start_time", 0),
                    end_time=seg_data.get("end_time", 0),
                    text=seg_data.get("text", ""),
                    confidence=seg_data.get("confidence"),
                    speaker_id=seg_data.get("speaker_id")
                ))

        return Transcription(
            id=model.id,
            video_id=model.video_id,
            status=model.status,
            language_code=model.language_code,
            full_text=model.full_text,
            segments=segments,
            confidence_score=model.confidence_score,
            processing_time=model.processing_time,
            model_used=model.model_used,
            extra_metadata=model.extra_metadata,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at
        )