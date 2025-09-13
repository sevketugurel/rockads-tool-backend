from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from infrastructure.database.connection import get_async_db
from application.services.dependency_injection import get_video_use_cases
from domain.entities.video import Video, VideoStatus
from domain.entities.transcription import Transcription
from application.use_cases.video_use_cases import VideoUseCases

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["videos"])


# Pydantic models for API responses
from pydantic import BaseModel
from datetime import datetime


class VideoResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    duration: Optional[float]
    status: str
    content_type: str
    language: Optional[str]
    description: Optional[str]
    is_advertisement: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, video: Video) -> "VideoResponse":
        return cls(
            id=video.id,
            filename=video.filename,
            original_filename=video.original_filename,
            file_size=video.file_size,
            duration=video.duration,
            status=video.status.value if hasattr(video.status, 'value') else video.status,
            content_type=video.content_type,
            language=video.language,
            description=video.description,
            is_advertisement=video.is_advertisement,
            created_at=video.created_at,
            updated_at=video.updated_at
        )


class TranscriptionSegmentResponse(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float]
    speaker_id: Optional[str]


class TranscriptionResponse(BaseModel):
    id: int
    video_id: int
    status: str
    language_code: str
    full_text: Optional[str]
    segments: Optional[List[TranscriptionSegmentResponse]]
    confidence_score: Optional[float]
    processing_time: Optional[float]
    model_used: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, transcription: Transcription) -> "TranscriptionResponse":
        segments = None
        if transcription.segments:
            segments = [
                TranscriptionSegmentResponse(
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    text=seg.text,
                    confidence=seg.confidence,
                    speaker_id=seg.speaker_id
                )
                for seg in transcription.segments
            ]

        return cls(
            id=transcription.id,
            video_id=transcription.video_id,
            status=transcription.status.value if hasattr(transcription.status, 'value') else transcription.status,
            language_code=transcription.language_code,
            full_text=transcription.full_text,
            segments=segments,
            confidence_score=transcription.confidence_score,
            processing_time=transcription.processing_time,
            model_used=transcription.model_used,
            error_message=transcription.error_message,
            created_at=transcription.created_at,
            updated_at=transcription.updated_at
        )


class VideoUploadResponse(BaseModel):
    message: str
    video: VideoResponse


class TranscriptionRequest(BaseModel):
    language_hint: Optional[str] = None


class ProcessingStatusResponse(BaseModel):
    video_id: int
    video_status: str
    transcription_status: Optional[str]
    language: Optional[str]
    duration: Optional[float]
    created_at: datetime
    updated_at: datetime
    transcription_confidence: Optional[float]
    processing_time: Optional[float]


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Upload a video file for processing

    Args:
        file: Video file to upload
        description: Optional description for the video
        session: Database session

    Returns:
        Upload confirmation with video details
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        if not file.content_type or not file.content_type.startswith("video/"):
            raise HTTPException(status_code=400, detail="File must be a video")

        # Read file content
        file_content = await file.read()

        # Get video use cases
        video_use_cases = get_video_use_cases(session)

        # Upload video
        video = await video_use_cases.upload_video(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            description=description
        )

        logger.info(f"Video uploaded successfully: {video.id}")

        return VideoUploadResponse(
            message="Video uploaded successfully",
            video=VideoResponse.from_entity(video)
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[VideoResponse])
async def get_all_videos(session: AsyncSession = Depends(get_async_db)):
    """Get all videos"""
    try:
        video_use_cases = get_video_use_cases(session)
        videos = await video_use_cases.get_all_videos()

        return [VideoResponse.from_entity(video) for video in videos]

    except Exception as e:
        logger.error(f"Error getting all videos: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    """Get video by ID"""
    try:
        video_use_cases = get_video_use_cases(session)
        video = await video_use_cases.get_video_by_id(video_id)

        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        return VideoResponse.from_entity(video)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{video_id}/transcribe", response_model=TranscriptionResponse)
async def transcribe_video(
    video_id: int,
    request: TranscriptionRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Start transcription process for a video

    This endpoint will start the transcription process in the background.
    Use the /videos/{video_id}/status endpoint to check progress.
    """
    try:
        video_use_cases = get_video_use_cases(session)

        # Check if video exists
        video = await video_use_cases.get_video_by_id(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Check if already transcribed
        existing_transcription = await video_use_cases.get_video_transcription(video_id)
        if existing_transcription and existing_transcription.status.value == "completed":
            return TranscriptionResponse.from_entity(existing_transcription)

        # Start transcription process
        transcription = await video_use_cases.transcribe_video(
            video_id=video_id,
            language_hint=request.language_hint
        )

        logger.info(f"Transcription started for video {video_id}")

        return TranscriptionResponse.from_entity(transcription)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting transcription for video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{video_id}/transcription", response_model=TranscriptionResponse)
async def get_video_transcription(
    video_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    """Get transcription for a video"""
    try:
        video_use_cases = get_video_use_cases(session)
        transcription = await video_use_cases.get_video_transcription(video_id)

        if not transcription:
            raise HTTPException(status_code=404, detail="Transcription not found")

        return TranscriptionResponse.from_entity(transcription)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcription for video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{video_id}/status", response_model=ProcessingStatusResponse)
async def get_video_status(
    video_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    """Get processing status for a video"""
    try:
        video_use_cases = get_video_use_cases(session)
        status_info = await video_use_cases.get_video_processing_status(video_id)

        return ProcessingStatusResponse(**status_info)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting status for video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{video_id}")
async def delete_video(
    video_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    """Delete a video and all associated data"""
    try:
        video_use_cases = get_video_use_cases(session)
        success = await video_use_cases.delete_video(video_id)

        if not success:
            raise HTTPException(status_code=404, detail="Video not found")

        return {"message": "Video deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")