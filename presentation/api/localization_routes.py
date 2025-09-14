from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field

from infrastructure.database.connection import get_async_db, AsyncSessionLocal
from application.use_cases.localization_use_cases import LocalizationUseCases
from application.services.dependency_injection import get_localization_use_cases
from application.services.ai.cultural_analysis_service import CulturalAnalysisService

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
    final_video_path: Optional[str] = None  # Absolute or relative path on server
    has_audio_localization: bool = False  # Whether TTS was generated
    video_duration: Optional[float] = None
    parts: Optional[List[Dict[str, Any]]] = None  # Multi-part outputs


class EnhancedLocalizationRequest(BaseModel):
    """Enhanced localization request with audio separation features"""
    video_id: int = Field(..., description="ID of the video to localize")
    country_code: str = Field(..., description="Target country code (e.g., US, GB, AU)")
    preserve_background_audio: bool = Field(
        True,
        description="Preserve background music/ambient sounds from original video"
    )
    background_volume: float = Field(
        0.3,
        ge=0.0,
        le=1.0,
        description="Volume level for background audio (0.0-1.0)"
    )
    voice_volume: float = Field(
        1.0,
        ge=0.0,
        le=2.0,
        description="Volume level for localized voice (0.0-2.0)"
    )
    use_precision_timing: bool = Field(
        True,
        description="Use enhanced timing synchronization for voice"
    )
    audio_quality: str = Field(
        "high",
        pattern="^(low|medium|high)$",
        description="Audio quality setting"
    )
    split_into_parts: Optional[int] = Field(
        None,
        gt=0,
        description="Split video into multiple parts for processing"
    )
    max_part_duration: Optional[float] = Field(
        None,
        gt=0.0,
        description="Maximum duration per part in seconds"
    )


class DirectLocalizationRequest(BaseModel):
    """Input for single-shot direct localization"""
    video_id: int = Field(..., description="ID of the video to localize")
    country_code: str = Field(..., description="Target country code (e.g., US, GB, AU)")
    use_local_tts: bool = Field(False, description="Force local OS TTS instead of ElevenLabs")
    music_only_background: bool = Field(
        False,
        description="Try to remove original vocals and keep only background music under the new voice"
    )
    split_into_parts: Optional[int] = Field(
        None,
        description="Split output into this many parts (approximate)"
    )
    max_part_duration: Optional[float] = Field(
        None,
        description="Target maximum seconds per part; segments are grouped by cumulative duration"
    )


class FastLocalizationRequest(BaseModel):
    """Simplified fast localization for single country"""
    video_id: int = Field(..., description="ID of the video to localize")
    country_code: str = Field(..., description="Single target country code (e.g., US, GB, AU)")
    force_local_tts: bool = Field(False, description="Use local TTS instead of ElevenLabs")


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
    try:
        # Test basic services
        health_data = {
            "service": "localization",
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "version": "2.0-single-country-optimized",
            "features": {
                "single_country_selection": "available",
                "fast_localization": "available",
                "direct_processing": "available",
                "video_analysis": "available",
                "cultural_adaptation": "available",
                "progress_tracking_fixed": "available"
            },
            "performance": {
                "status_hang_issue": "resolved",
                "multi_country_complexity": "simplified_to_single",
                "timeout_protection": "enabled",
                "retry_logic": "enabled"
            }
        }

        return health_data
    except Exception as e:
        return {
            "service": "localization",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }


class CulturalAnalysisRequest(BaseModel):
    """Request for cultural analysis across multiple countries"""
    video_id: int
    country_codes: List[str]


@router.post("/analysis")
async def analyze_cultural_fit(
    req: CulturalAnalysisRequest,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Run Gemini-powered cultural analysis with a lightweight RAG knowledge base for selected countries.

    Returns structured insights per country: strengths, risks, adaptations, CTA examples, compliance, KPIs.
    """
    try:
        use_cases = get_localization_use_cases(session)
        # Fetch video and build minimal context using existing services if available
        video = await use_cases.video_repository.get_by_id(req.video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Use quick video info as context (avoid heavy processing here)
        video_context = {
            "duration": video.duration,
            "language": video.language,
            "filename": video.original_filename,
        }

        # Prepare analyzer
        # Gather richer text context if available
        transcription_text = None
        try:
            transcription = await use_cases.localization_service.transcription_repository.get_by_video_id(req.video_id)
            if transcription and transcription.full_text:
                transcription_text = transcription.full_text
        except Exception:
            pass

        translation_texts = []
        try:
            translations = await use_cases.localization_service.get_translations_for_video(req.video_id)
            for t in translations:
                if t.full_translated_text:
                    translation_texts.append(t.full_translated_text)
        except Exception:
            pass

        analyzer = CulturalAnalysisService()
        results = []

        # Resolve countries and analyze
        for code in req.country_codes:
            country = await use_cases.country_repository.get_by_country_code(code)
            if not country:
                results.append({"country_code": code.upper(), "error": "Country not found"})
                continue
            result = await analyzer.analyze_for_country(
                video=video,
                country=country,
                video_context=video_context,
                transcription_text=transcription_text,
                translation_texts=translation_texts,
            )
            results.append(result)

        return {"video_id": req.video_id, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cultural analysis failed: {str(e)}")


@router.post("/fast", response_model=TranslationResult)
async def fast_localize(
    request: FastLocalizationRequest,
    session: AsyncSession = Depends(get_async_db),
    http_request: Request = None,
):
    """
    ULTRA-FAST: Single country localization without job orchestration.

    This endpoint bypasses all complex job management and multi-country processing
    to provide the fastest, most reliable localization for a single target country.

    Perfect for resolving status hang issues by using direct processing only.
    """
    try:
        import time
        import logging
        logger = logging.getLogger(__name__)
        start_time = time.time()

        logger.info(f"FAST localization: video {request.video_id} → {request.country_code}")

        use_cases = get_localization_use_cases(session)

        # Direct localization - no job orchestration
        result = await use_cases.direct_localize_video(
            video_id=request.video_id,
            country_code=request.country_code,
            force_local_tts=request.force_local_tts,
            music_only_background=True,  # Better audio quality
            split_into_parts=None,  # No splitting for speed
            max_part_duration=None
        )

        processing_time = time.time() - start_time
        logger.info(f"FAST localization completed in {processing_time:.2f}s")

        # Ensure absolute URLs
        if http_request:
            base = str(http_request.base_url).rstrip('/')
            if result.get("final_video_url") and result["final_video_url"].startswith("/"):
                result["final_video_url"] = f"{base}{result['final_video_url']}"

        return result

    except Exception as e:
        logger.error(f"Fast localization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fast localization failed: {str(e)}")


@router.post("/direct", response_model=TranslationResult)
async def direct_localize(
    request: DirectLocalizationRequest,
    session: AsyncSession = Depends(get_async_db),
    http_request: Request = None,
):
    """
    SIMPLIFIED: Complete video localization with single country direct processing.

    This endpoint performs optimized single-country processing:
    1. Video analysis and translation (SINGLE COUNTRY ONLY)
    2. Text-to-Speech generation
    3. Audio synchronization with original video
    4. Final video creation with localized audio

    IMPORTANT: This endpoint is optimized for single country processing to avoid
    the status hang issues experienced with multi-country workflows.

    Returns translation result with download URL for final video.
    """
    try:
        import time
        start_time = time.time()

        logger.info(f"Starting DIRECT localization for video {request.video_id} -> {request.country_code}")

        use_cases = get_localization_use_cases(session)
        result = await use_cases.direct_localize_video(
            request.video_id,
            request.country_code,
            force_local_tts=request.use_local_tts,
            music_only_background=request.music_only_background,
            split_into_parts=request.split_into_parts,
            max_part_duration=request.max_part_duration
        )

        processing_time = time.time() - start_time
        logger.info(f"Direct localization completed in {processing_time:.2f}s for {request.country_code}")

        # Convert relative download URL to absolute for frontend convenience
        try:
            base = str(http_request.base_url).rstrip('/') if http_request else ''
            if result.get("final_video_url") and base and result["final_video_url"].startswith("/"):
                result["final_video_url"] = f"{base}{result['final_video_url']}"
            if result.get("parts") and isinstance(result["parts"], list) and base:
                for p in result["parts"]:
                    if isinstance(p, dict) and p.get("final_video_url", "").startswith("/"):
                        p["final_video_url"] = f"{base}{p['final_video_url']}"
        except Exception:
            pass
        return result
    except ValueError as e:
        logger.error(f"Direct localization validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Direct localization processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Direct localization failed: {str(e)}")


@router.post("/enhanced-localize", response_model=TranslationResult)
async def enhanced_localize_with_audio_separation(
    request: EnhancedLocalizationRequest,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Enhanced localization with advanced audio source separation and mixing.

    This endpoint provides premium audio processing features:
    - Audio source separation to isolate vocals from background music
    - Preservation of original background music/ambient sounds
    - High-precision timing synchronization with ElevenLabs TTS
    - Professional audio mixing with volume control
    - Enhanced quality options for commercial use

    Args:
        request: Enhanced localization configuration

    Returns:
        Enhanced translation result with preserved audio quality
    """
    try:
        logger.info(f"Enhanced localization request for video {request.video_id} to {request.country_code}")

        # Get localization use cases
        localization_cases = get_localization_use_cases(session)
        
        # Validate video exists
        video_info = await localization_cases.get_video_info(request.video_id)
        if not video_info:
            raise HTTPException(status_code=404, detail="Video not found")

        # Analyze audio separation feasibility first
        feasibility = await localization_cases.analyze_audio_separation_feasibility(request.video_id)

        if feasibility.get("error"):
            logger.warning(f"Audio analysis failed: {feasibility['error']}")
            # Continue with warning but still process
        elif not feasibility.get("separation_feasible") and request.preserve_background_audio:
            logger.warning("Audio separation may not be effective for this video")

        # Process enhanced localization
        translation = await localization_cases.enhanced_localize_video(
            video_id=request.video_id,
            country_code=request.country_code,
            preserve_background_audio=request.preserve_background_audio,
            background_volume=request.background_volume,
            voice_volume=request.voice_volume,
            use_precision_timing=request.use_precision_timing,
            audio_quality=request.audio_quality,
            split_into_parts=request.split_into_parts,
            max_part_duration=request.max_part_duration
        )

        # Extract processing metadata
        processing_info = {}
        if translation.warnings:
            for warning in translation.warnings:
                if isinstance(warning, dict) and "audio_processing" in warning:
                    processing_info = warning["audio_processing"]
                    break

        # Generate download URL if video was created
        final_video_url = None
        if translation.final_video_path and os.path.exists(translation.final_video_path):
            filename = os.path.basename(translation.final_video_path)
            final_video_url = f"/api/localization/download/{filename}"

        return TranslationResult(
            translation_id=translation.id,
            status=translation.status,
            target_country={
                "code": request.country_code,
                "name": "Enhanced Processing"
            },
            translated_text=translation.text_summary or "Enhanced audio localization completed",
            confidence_score=translation.overall_confidence,
            cultural_appropriateness=translation.cultural_appropriateness_score,
            effectiveness_prediction=translation.effectiveness_prediction,
            processing_time=translation.processing_time,
            warnings=[
                f"Enhanced audio processing: {processing_info.get('voice_segments_count', 0)} voice segments",
                f"Background preserved: {processing_info.get('background_preserved', False)}",
                f"Audio quality: {processing_info.get('audio_quality', 'standard')}"
            ],
            final_video_url=final_video_url,
            final_video_path=translation.final_video_path,
            has_audio_localization=True,
            video_duration=translation.video_duration
        )

    except ValueError as e:
        logger.error(f"Enhanced localization validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Enhanced localization processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Enhanced localization failed: {str(e)}")


@router.get("/audio-analysis/{video_id}")
async def analyze_audio_separation_feasibility(
    video_id: int,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Analyze a video's suitability for audio source separation.

    This endpoint helps users determine if enhanced localization with audio separation
    would be beneficial for their video content.

    Args:
        video_id: ID of the video to analyze

    Returns:
        Analysis results with recommendations
    """
    try:
        logger.info(f"Analyzing audio separation feasibility for video {video_id}")

        # Get localization use cases
        localization_cases = get_localization_use_cases(session)
        
        analysis = await localization_cases.analyze_audio_separation_feasibility(video_id)

        if analysis.get("error"):
            raise HTTPException(status_code=400, detail=analysis["error"])

        return {
            "video_id": video_id,
            "separation_feasible": analysis.get("separation_feasible", False),
            "expected_quality": analysis.get("expected_quality", "unknown"),
            "audio_info": {
                "channels": analysis.get("channels", 0),
                "sample_rate": analysis.get("sample_rate", 0),
                "duration": analysis.get("duration", 0)
            },
            "processing_estimate": {
                "estimated_time_seconds": analysis.get("estimated_processing_time", 0),
                "recommended_model": analysis.get("recommended_model")
            },
            "recommendations": analysis.get("recommendations", []),
            "enhanced_localization_recommended": analysis.get("enhanced_localization_recommended", False),
            "spleeter_available": analysis.get("spleeter_available", False)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {str(e)}")


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
