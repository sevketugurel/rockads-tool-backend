from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import os

from pydantic import BaseModel, Field

from infrastructure.database.connection import get_async_db, AsyncSessionLocal
from application.use_cases.localization_use_cases import LocalizationUseCases
from application.services.dependency_injection import get_localization_use_cases

router = APIRouter(prefix="/api/localization", tags=["localization"])


# Request/Response Models
class LocalizationRequest(BaseModel):
    """Request model for creating localization job"""
    video_id: int = Field(..., description="ID of the video to localize")
    target_countries: List[str] = Field(..., min_items=1, description="List of target country codes (e.g., ['US', 'GB', 'AU'])")
    user_id: Optional[int] = Field(None, description="Optional user ID")
    preferences: Optional[Dict[str, Any]] = Field(
        None,
        description="Localization preferences",
        example={
            "analysis_depth": "comprehensive",
            "cultural_sensitivity": "high",
            "brand_consistency": "strict",
            "preserve_brand_elements": True,
            "adapt_for_culture": True,
            "maintain_video_timing": True
        }
    )


class LocalizationJobResponse(BaseModel):
    """Response model for localization job"""
    job_id: int
    video_id: int
    status: str
    target_countries: List[str]
    progress_percentage: float
    estimated_completion: Optional[datetime]
    created_at: datetime


class CountryInfo(BaseModel):
    """Model for country information"""
    id: int
    country_code: str
    country_name: str
    language_code: str
    language_name: str
    dialect: str
    communication_style: str
    marketing_preferences: str
    priority: int


class LanguageGroup(BaseModel):
    """Model for language-grouped countries"""
    language_code: str
    language_name: str
    countries: List[CountryInfo]


class TranslationResult(BaseModel):
    """Model for translation results"""
    translation_id: int
    status: str
    target_country: Optional[Dict[str, str]] = None
    translated_text: Optional[str] = None
    confidence_score: Optional[float] = None
    cultural_appropriateness: Optional[float] = None
    effectiveness_prediction: Optional[float] = None
    processing_time: Optional[float] = None
    warnings: List[str] = []
    final_video_url: Optional[str] = None  # URL to download final localized video
    has_audio_localization: bool = False  # Whether TTS was generated
    video_duration: Optional[float] = None


class DirectLocalizationRequest(BaseModel):
    """Input for single-shot direct localization"""
    video_id: int = Field(..., description="ID of the video to localize")
    country_code: str = Field(..., description="Target country code (e.g., US, GB, AU)")
    use_local_tts: bool = Field(False, description="Force local OS TTS instead of ElevenLabs")
    music_only_background: bool = Field(
        False,
        description="Try to remove original vocals and keep only background music under the new voice"
    )


# No need for dependency function - we'll create use cases directly in routes


# Routes
@router.get("/countries", response_model=Union[List[CountryInfo], List[LanguageGroup]])
async def get_available_countries(
    group_by_language: bool = Query(False, description="Group countries by language"),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Get available countries for localization

    Returns a list of countries with cultural context information that can be used
    for video localization. Each country includes dialect information, cultural
    preferences, and marketing context.
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        countries = await localization_use_cases.get_available_countries_for_localization(
            group_by_language=group_by_language
        )
        return countries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get countries: {str(e)}")


@router.get("/languages", response_model=List[LanguageGroup])
async def get_countries_by_language(
    session: AsyncSession = Depends(get_async_db)
):
    """
    Get countries grouped by language

    Returns countries organized by language, useful for UI selection where users
    might want to see all variants of a language (e.g., US English, UK English, Australian English).
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        language_groups = await localization_use_cases.get_available_countries_for_localization(
            group_by_language=True
        )
        return language_groups
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get language groups: {str(e)}")


@router.post("/jobs", response_model=LocalizationJobResponse)
async def create_localization_job(
    request: LocalizationRequest,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Create a new localization job

    Creates a localization job that will analyze the video content holistically and
    create culturally appropriate translations for each target country. The system
    considers visual context, cultural nuances, and advertising effectiveness.
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        job = await localization_use_cases.create_localization_request(
            video_id=request.video_id,
            target_countries=request.target_countries,
            user_id=request.user_id,
            preferences=request.preferences
        )

        return LocalizationJobResponse(
            job_id=job.id,
            video_id=job.video_id,
            status=job.status,
            target_countries=request.target_countries,
            progress_percentage=job.progress_percentage,
            estimated_completion=job.estimated_completion,
            created_at=job.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create localization job: {str(e)}")


@router.post("/jobs/{job_id}/start")
async def start_localization_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Start processing a localization job

    Initiates the complete localization pipeline including:
    1. Video content analysis (visual + audio)
    2. Cultural context assessment
    3. Context-aware translation for each target country
    4. Cultural appropriateness validation
    5. Advertising effectiveness optimization
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        # Validate job exists before scheduling
        job = await localization_use_cases.localization_job_repository.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Localization job {job_id} not found")

        # Use a fresh session in background context to avoid closed-session issues
        async def _run_localization(job_id_: int):
            async with AsyncSessionLocal() as bg_session:
                use_cases = get_localization_use_cases(bg_session)
                await use_cases.start_localization_process(job_id_)

        background_tasks.add_task(_run_localization, job_id)

        return {
            "message": f"Localization job {job_id} started",
            "job_id": job_id,
            "status": "processing_started"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start localization job: {str(e)}")


@router.get("/jobs/{job_id}")
async def get_localization_job_status(
    job_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Get detailed status of a localization job

    Returns comprehensive information about the job including:
    - Overall progress and status
    - Individual translation statuses
    - Quality metrics and scores
    - Cost estimates
    - Error details if any
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        job_details = await localization_use_cases.get_localization_job_details(job_id)
        return job_details
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.get("/jobs/{job_id}/translations")
async def get_job_translations(
    job_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Get all translations for a specific job

    Returns detailed information about each translation created by the job,
    including cultural adaptations and effectiveness scores.
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        job_details = await localization_use_cases.get_localization_job_details(job_id)
        return {
            "job_id": job_id,
            "translations": job_details.get("translations", [])
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job translations: {str(e)}")


@router.get("/translations/{translation_id}", response_model=TranslationResult)
async def get_translation_result(
    translation_id: int,
    include_analysis: bool = Query(False, description="Include detailed video and cultural analysis"),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Get detailed translation result

    Returns the complete translation result including:
    - Translated text with timing segments
    - Cultural adaptations made
    - Confidence and effectiveness scores
    - Optional detailed analysis of video context and cultural considerations
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        translation = await localization_use_cases.get_translation_result(
            translation_id,
            include_analysis=include_analysis
        )
        return translation
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get translation: {str(e)}")


@router.get("/videos/{video_id}/localizations")
async def get_video_localizations(
    video_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Get all localizations for a specific video

    Returns a comprehensive overview of all localization efforts for a video,
    including completed translations, ongoing jobs, and summary statistics.
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        localizations = await localization_use_cases.get_video_localizations(video_id)
        return localizations
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get video localizations: {str(e)}")


@router.post("/translations/{translation_id}/retry")
async def retry_failed_translation(
    translation_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Retry a failed translation

    Attempts to retry a translation that failed during processing. This will
    restart the complete analysis and translation process for that specific
    country target.
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        # Add retry to background tasks
        background_tasks.add_task(
            localization_use_cases.retry_failed_localization,
            translation_id
        )

        return {
            "message": f"Translation {translation_id} retry initiated",
            "translation_id": translation_id,
            "status": "retry_started"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retry translation: {str(e)}")


@router.delete("/jobs/{job_id}")
async def cancel_localization_job(
    job_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Cancel a localization job

    Cancels a localization job if it's still in progress. Already completed
    translations will not be affected.
    """
    try:
        localization_use_cases = get_localization_use_cases(session)
        result = await localization_use_cases.cancel_localization_job(job_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.get("/analytics/summary")
async def get_localization_analytics(
    video_id: Optional[int] = Query(None, description="Filter by specific video"),
    country_code: Optional[str] = Query(None, description="Filter by country code"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Get localization analytics and summary statistics

    Returns analytics about localization performance, including:
    - Success rates by country
    - Average quality scores
    - Processing times
    - Most popular target countries
    - Cultural adaptation trends
    """
    # This would be implemented based on business requirements
    # For now, return a placeholder structure
    return {
        "message": "Analytics endpoint - to be implemented based on business requirements",
        "filters": {
            "video_id": video_id,
            "country_code": country_code,
            "date_from": date_from,
            "date_to": date_to
        }
    }


@router.get("/health")
async def localization_health_check():
    """
    Health check endpoint for localization service

    Returns the health status of the localization system and its dependencies.
    """
    return {
        "service": "localization",
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "features": {
            "country_selection": "available",
            "video_analysis": "available",
            "cultural_adaptation": "available",
            "effectiveness_optimization": "available"
        }
    }


@router.post("/direct", response_model=TranslationResult)
async def direct_localize(
    request: DirectLocalizationRequest,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Complete video localization with TTS and final video generation.

    This endpoint performs:
    1. Video analysis and translation
    2. Text-to-Speech generation with ElevenLabs
    3. Audio synchronization with original video
    4. Final video creation with localized audio

    Returns translation result with download URL for final video.
    """
    try:
        use_cases = get_localization_use_cases(session)
        result = await use_cases.direct_localize_video(
            request.video_id,
            request.country_code,
            force_local_tts=request.use_local_tts,
            music_only_background=request.music_only_background
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Direct localization failed: {str(e)}")


@router.get("/download/{filename}")
async def download_localized_video(filename: str):
    """
    Download a localized video file

    Args:
        filename: Name of the localized video file

    Returns:
        FileResponse with the video file
    """
    try:
        from core.config.settings import settings

        # Construct file path
        file_path = os.path.join(settings.output_dir, filename)

        # Security check - ensure file is within output directory
        if not os.path.abspath(file_path).startswith(os.path.abspath(settings.output_dir)):
            raise HTTPException(status_code=400, detail="Invalid file path")

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        # Return the file
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
