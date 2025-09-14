import asyncio
import logging
from typing import List, Dict, Any, Optional
import os
from datetime import datetime, timedelta

from domain.entities.video import Video
from domain.entities.transcription import Transcription
from domain.entities.translation import Translation, TranslationJob, TranslationStatus
from domain.entities.country import Country
from domain.entities.localization_job import LocalizationJob, LocalizationJobStatus

from domain.repositories.video_repository import VideoRepository
from domain.repositories.transcription_repository import TranscriptionRepository
from domain.repositories.translation_repository import TranslationRepository
from domain.repositories.country_repository import CountryRepository
from domain.repositories.localization_job_repository import LocalizationJobRepository

from application.services.ai.translation_service import TranslationService
from application.services.audio.audio_separation_service import AudioSeparationService
from application.services.audio.audio_mixing_service import AudioMixingService, AudioMixConfig
from application.services.ai.elevenlabs_tts_service import ElevenLabsTTSService

logger = logging.getLogger(__name__)


class LocalizationService:
    """
    Orchestrates the complete video localization workflow with cultural context awareness
    """

    def __init__(
        self,
        video_repository: VideoRepository,
        transcription_repository: TranscriptionRepository,
        translation_repository: TranslationRepository,
        country_repository: CountryRepository,
        localization_job_repository: LocalizationJobRepository,
        translation_service: TranslationService
    ):
        self.video_repository = video_repository
        self.transcription_repository = transcription_repository
        self.translation_repository = translation_repository
        self.country_repository = country_repository
        self.localization_job_repository = localization_job_repository
        self.translation_service = translation_service

        # Initialize new audio processing services
        self.audio_separation_service = AudioSeparationService()
        self.audio_mixing_service = AudioMixingService()
        self.elevenlabs_service = None
        try:
            self.elevenlabs_service = ElevenLabsTTSService()
        except Exception as e:
            logger.warning(f"ElevenLabs service not available: {e}")

    async def create_localization_job(
        self,
        video_id: int,
        target_country_codes: List[str],
        user_id: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LocalizationJob:
        """
        Create a new localization job for multiple countries

        Args:
            video_id: ID of the video to localize
            target_country_codes: List of target country codes (e.g., ['US', 'GB', 'AU'])
            user_id: Optional user ID who initiated the job
            config: Optional configuration settings

        Returns:
            Created LocalizationJob
        """
        try:
            # Validate video exists
            video = await self.video_repository.get_by_id(video_id)
            if not video:
                raise ValueError(f"Video {video_id} not found")

            # Validate and get target countries (store as IDs)
            target_countries: List[int] = []
            for country_code in target_country_codes:
                country = await self.country_repository.get_by_country_code(country_code)
                if not country:
                    raise ValueError(f"Country {country_code} not found")
                target_countries.append(country.id)

            # Create localization job
            localization_job = LocalizationJob(
                video_id=video_id,
                user_id=user_id,
                status=LocalizationJobStatus.CREATED,
                source_language=video.language or "auto",
                target_languages=[],
                target_countries=target_countries,
                preserve_timing=(config.get("maintain_video_timing", True) if config else True),
                adjust_for_culture=(config.get("adjust_for_culture", True) if config else True),
                voice_tone=(config.get("voice_tone", "professional") if config else "professional")
            )

            # Estimate completion time
            estimated_minutes = len(target_country_codes) * 10  # Rough estimate
            localization_job.estimated_completion = datetime.utcnow() + timedelta(minutes=estimated_minutes)

            # Save to database
            localization_job = await self.localization_job_repository.create(localization_job)

            logger.info(f"Created localization job {localization_job.id} for video {video_id}")
            return localization_job

        except Exception as e:
            logger.error(f"Failed to create localization job: {str(e)}")
            raise

    async def process_localization_job(self, job_id: int, direct_mode: bool = True) -> LocalizationJob:
        """
        Process a complete localization job

        Args:
            job_id: ID of the localization job

        Returns:
            Updated LocalizationJob
        """
        job = await self.localization_job_repository.get_by_id(job_id)
        if not job:
            raise ValueError(f"Localization job {job_id} not found")

        try:
            logger.info(f"Starting processing of localization job {job_id}")

            # Update status to processing
            video = await self.video_repository.get_by_id(job.video_id)

            if direct_mode:
                job.status = LocalizationJobStatus.TRANSLATING
                # Ensure a placeholder transcription exists to satisfy DB schema
                transcription = await self._ensure_pseudo_transcription(video)
                job.transcription_id = transcription.id
            else:
                job.status = LocalizationJobStatus.TRANSCRIBING
                await self.localization_job_repository.update(job)
                transcription = await self._ensure_transcribed(video)
                if not transcription or transcription.status != "completed":
                    raise Exception("Video transcription failed or incomplete")
                job.status = LocalizationJobStatus.TRANSLATING
                job.transcription_id = transcription.id
            await self.localization_job_repository.update(job)

            # Process translations for each target country
            translations: List[int] = []
            total_countries = len(job.target_countries or [])

            # If no target countries are configured, treat as a no-op completion
            # rather than a failure to avoid confusing UX in status checks.
            if total_countries == 0:
                job.translation_ids = []
                job.status = LocalizationJobStatus.COMPLETED
                job.progress_percentage = 100.0
                await self.localization_job_repository.update(job)
                logger.info(
                    f"Localization job {job_id} completed with no target countries (no-op)"
                )
                return job

            # Track counts locally to avoid relying on DB columns
            success_count = 0
            failure_count = 0

            for i, country_id in enumerate(job.target_countries or []):
                try:
                    logger.info(f"Processing translation {i+1}/{total_countries} for country {country_id}")

                    # Update progress at start of processing
                    start_progress = (i / total_countries) * 90  # Reserve 10% for final steps
                    job.progress_percentage = start_progress + 5  # Add 5% for starting this country
                    await self.localization_job_repository.update(job)

                    # Get country details
                    country = await self.country_repository.get_by_id(country_id)
                    if not country:
                        logger.warning(f"Country {country_id} not found, skipping")
                        failure_count += 1
                        continue

                    # Update progress before translation
                    job.progress_percentage = start_progress + 20  # 20% for country validation
                    await self.localization_job_repository.update(job)

                    # Create and process translation
                    translation = await self._process_single_translation(
                        video, transcription, country, job, direct_mode=direct_mode
                    )

                    if translation.status == TranslationStatus.COMPLETED:
                        translations.append(translation.id)
                        success_count += 1
                        # Full progress for this country
                        job.progress_percentage = ((i + 1) / total_countries) * 90
                    else:
                        failure_count += 1
                        # Partial progress even on failure to avoid hangs
                        job.progress_percentage = ((i + 1) / total_countries) * 90

                    await self.localization_job_repository.update(job)

                except Exception as e:
                    logger.error(f"Translation failed for country {country_id}: {str(e)}")
                    failure_count += 1
                    if not job.error_details:
                        job.error_details = []
                    job.error_details.append(f"Country {country_id}: {str(e)}")

            # Update final job status
            job.translation_ids = translations
            job.status = LocalizationJobStatus.COMPLETED if success_count > 0 else LocalizationJobStatus.FAILED
            job.progress_percentage = 100.0

            await self.localization_job_repository.update(job)

            logger.info(f"Completed localization job {job_id}: {success_count} successes, {failure_count} failures")
            return job

        except Exception as e:
            logger.error(f"Localization job {job_id} failed: {str(e)}")
            job.status = LocalizationJobStatus.FAILED
            if not job.error_details:
                job.error_details = []
            job.error_details.append(f"Job failed: {str(e)}")
            await self.localization_job_repository.update(job)
            raise

    async def get_available_countries(self, active_only: bool = True) -> List[Country]:
        """
        Get list of available countries for localization

        Args:
            active_only: Whether to return only active countries

        Returns:
            List of Country objects
        """
        return await self.country_repository.get_all_active() if active_only else await self.country_repository.get_all()

    async def get_localization_job_status(self, job_id: int) -> Dict[str, Any]:
        """
        Get detailed status of a localization job

        Args:
            job_id: ID of the localization job

        Returns:
            Dictionary with detailed status information
        """
        job = await self.localization_job_repository.get_by_id(job_id)
        if not job:
            raise ValueError(f"Localization job {job_id} not found")

        # Get translations details
        translation_details = []
        success_count = 0
        failure_count = 0
        if job.translation_ids:
            for translation_id in job.translation_ids:
                translation = await self.translation_repository.get_by_id(translation_id)
                if translation:
                    country = await self.country_repository.get_by_id(translation.country_id)
                    # Try to expose downloadable video URL if exists
                    final_video_url = None
                    final_video_path = None
                    try:
                        # If path was persisted, use it
                        if getattr(translation, "final_video_path", None):
                            from core.config.settings import settings
                            import os
                            filename = os.path.basename(translation.final_video_path)
                            candidate = os.path.join(settings.output_dir, filename)
                            if os.path.exists(candidate):
                                final_video_url = f"/api/localization/download/{filename}"
                                final_video_path = candidate
                        else:
                            # Fallback: infer by filename pattern <original_stem>_<CC>_*.mp4
                            video = await self.video_repository.get_by_id(job.video_id)
                            if video and country and country.country_code:
                                from core.config.settings import settings
                                stems = [
                                    os.path.splitext(video.original_filename or "")[0],
                                    os.path.splitext(video.filename or "")[0],
                                ]
                                cc = country.country_code
                                out_dir = settings.output_dir
                                if os.path.isdir(out_dir):
                                    matches = [f for f in os.listdir(out_dir) if f.endswith(".mp4") and any(
                                        f.startswith(f"{s}_{cc}_") for s in stems if s
                                    )]
                                    if matches:
                                        # pick most recent
                                        matches.sort(key=lambda f: os.path.getmtime(os.path.join(out_dir, f)), reverse=True)
                                        choice = matches[0]
                                        final_video_url = f"/api/localization/download/{choice}"
                                        final_video_path = os.path.join(out_dir, choice)
                    except Exception:
                        pass
                    if translation.status == TranslationStatus.COMPLETED:
                        success_count += 1
                    elif translation.status == TranslationStatus.FAILED:
                        failure_count += 1
                    translation_details.append({
                        "translation_id": translation_id,
                        "country_name": country.country_name if country else "Unknown",
                        "country_code": country.country_code if country else "Unknown",
                        "status": translation.status,
                        "confidence": translation.overall_confidence,
                        "cultural_score": translation.cultural_appropriateness_score,
                        "effectiveness": translation.effectiveness_prediction,
                        "final_video_url": final_video_url,
                        "final_video_path": final_video_path
                    })

        return {
            "job_id": job_id,
            "status": job.status,
            "progress_percentage": job.progress_percentage,
            "success_count": success_count,
            "failure_count": failure_count,
            "estimated_completion": job.estimated_completion,
            "error_details": job.error_details,
            "translations": translation_details,
            "created_at": job.created_at,
            "updated_at": job.updated_at
        }

    async def get_translation_by_id(self, translation_id: int) -> Optional[Translation]:
        """Get translation by ID with full details"""
        return await self.translation_repository.get_by_id(translation_id)

    async def get_translations_for_video(self, video_id: int) -> List[Translation]:
        """Get all translations for a video"""
        return await self.translation_repository.get_by_video_id(video_id)

    async def retry_failed_translation(self, translation_id: int) -> Translation:
        """
        Retry a failed translation

        Args:
            translation_id: ID of the failed translation

        Returns:
            Updated Translation object
        """
        translation = await self.translation_repository.get_by_id(translation_id)
        if not translation:
            raise ValueError(f"Translation {translation_id} not found")

        if translation.status != TranslationStatus.FAILED:
            raise ValueError(f"Translation {translation_id} is not in failed status")

        # Get related entities
        video = await self.video_repository.get_by_id(translation.video_id)
        transcription = await self.transcription_repository.get_by_id(translation.transcription_id)
        country = await self.country_repository.get_by_id(translation.country_id)

        if not all([video, transcription, country]):
            raise ValueError("Required entities not found for translation retry")

        # Reset translation status and retry
        translation.status = TranslationStatus.PENDING
        translation.error_message = None
        translation.warnings = []
        await self.translation_repository.update(translation)

        # Process the translation again (provide minimal job config)
        job_config = LocalizationJob(
            video_id=video.id,
            user_id=None,
            status=LocalizationJobStatus.CREATED,
            source_language=transcription.language_code or (video.language or "auto"),
            target_languages=[],
            target_countries=[country.id],
            preserve_timing=True,
            adjust_for_culture=True,
            voice_tone="professional"
        )

        updated_translation = await self._process_single_translation(
            video, transcription, country, job_config, direct_mode=True
        )

        return updated_translation

    async def direct_localize_with_audio_separation(
        self,
        video_id: int,
        country_code: str,
        preserve_background_audio: bool = True,
        background_volume: float = 0.3,
        voice_volume: float = 1.0,
        use_precision_timing: bool = True,
        audio_quality: str = "high",
        split_into_parts: Optional[int] = None,
        max_part_duration: Optional[float] = None
    ) -> Translation:
        """
        Advanced localization with audio source separation and mixing

        Args:
            video_id: ID of the video to localize
            country_code: Target country code
            preserve_background_audio: Whether to preserve background music/ambient sounds
            background_volume: Volume level for background audio (0.0-1.0)
            voice_volume: Volume level for new voice (0.0-2.0)
            use_precision_timing: Use enhanced timing synchronization
            audio_quality: Audio quality setting ("low", "medium", "high")
            split_into_parts: Optional number of parts to split video into
            max_part_duration: Optional maximum duration per part

        Returns:
            Translation object with enhanced audio processing
        """
        try:
            logger.info(f"Starting advanced localization with audio separation for video {video_id}")

            # Fetch required entities
            video = await self.video_repository.get_by_id(video_id)
            if not video:
                raise ValueError("Video not found")

            country = await self.country_repository.get_by_country_code(country_code)
            if not country:
                raise ValueError("Country not found")

            # Ensure a placeholder transcription
            transcription = await self._ensure_pseudo_transcription(video)

            # Step 1: Extract audio from video if needed
            video_audio_path = await self._extract_video_audio(video.file_path)
            if not video_audio_path:
                raise Exception("Failed to extract audio from video")

            # Step 2: Audio source separation (if preserving background)
            separated_audio = None
            if preserve_background_audio:
                separated_audio = await self.audio_separation_service.separate_audio_sources(
                    video_audio_path, model_type="2stems"  # vocals + accompaniment
                )

            # Step 3: Get localized translation with segments
            base_translation = await self.translation_service.direct_localize_video(
                video.file_path,
                country,
                skip_tts=True  # We'll handle TTS separately
            )

            if not base_translation.segments:
                raise Exception("No segments generated for translation")

            # Step 4: Generate localized speech with precision timing
            voice_segments = []
            if self.elevenlabs_service and use_precision_timing:
                voice_segments = await self.elevenlabs_service.generate_speech_for_segments_with_precision(
                    base_translation.segments,
                    country.language_code,
                    country_code,
                    str(self.audio_mixing_service.temp_dir)
                )
            else:
                # Fallback to standard generation
                voice_segments = await self._generate_voice_segments_standard(
                    base_translation.segments, country, country_code
                )

            # Step 5: Mix audio tracks
            final_audio_path = await self._create_final_mixed_audio(
                voice_segments,
                separated_audio,
                video_audio_path,
                base_translation.video_duration,
                preserve_background_audio,
                background_volume,
                voice_volume,
                audio_quality
            )

            # Step 6: Create final video with mixed audio
            final_video_path = await self._create_final_video_with_audio(
                video.file_path, final_audio_path, video_id, country_code
            )

            # Update translation record
            base_translation.final_video_path = final_video_path
            base_translation.status = "completed"
            base_translation.country_id = country.id

            # Add processing metadata
            base_translation.warnings = base_translation.warnings or []
            base_translation.warnings.append({
                "audio_processing": {
                    "background_preserved": preserve_background_audio,
                    "precision_timing": use_precision_timing,
                    "voice_segments_count": len(voice_segments),
                    "audio_quality": audio_quality,
                    "background_volume": background_volume,
                    "voice_volume": voice_volume
                }
            })

            # Save to database
            existing = await self.translation_repository.get_by_video_and_country(video.id, country.id)
            if existing:
                base_translation.id = existing.id
                await self.translation_repository.update(base_translation)
                return await self.translation_repository.get_by_id(existing.id)
            else:
                created = await self.translation_repository.create(base_translation)
                return created

        except Exception as e:
            logger.error(f"Advanced localization failed: {str(e)}")
            raise

    async def direct_localize(
        self,
        video_id: int,
        country_code: str,
        force_local_tts: bool = False,
        music_only_background: bool = False,
        split_into_parts: Optional[int] = None,
        max_part_duration: Optional[float] = None
    ) -> Translation:
        """Simplified single-shot localization: video -> country-specific translation.

        - No job orchestration
        - Reuses existing translation record if present
        - Uses direct video context (no transcription dependency)
        """
        # Fetch required entities
        video = await self.video_repository.get_by_id(video_id)
        if not video:
            raise ValueError("Video not found")

        country = await self.country_repository.get_by_country_code(country_code)
        if not country:
            raise ValueError("Country not found")

        # Ensure a placeholder transcription (DB schema requires)
        transcription = await self._ensure_pseudo_transcription(video)

        # Minimal job config for internal API compatibility
        from domain.entities.localization_job import LocalizationJob, LocalizationJobStatus
        job_stub = LocalizationJob(
            video_id=video.id,
            user_id=None,
            status=LocalizationJobStatus.TRANSLATING,
            source_language=video.language or "auto",
            target_languages=[],
            target_countries=[country.id],
            preserve_timing=True,
            adjust_for_culture=True,
            voice_tone="professional"
        )

        # Process the translation directly (video-only context)
        # If no splitting requested, run standard direct pipeline
        if not split_into_parts and not max_part_duration:
            translation = await self._process_single_translation(
                video,
                transcription,
                country,
                job_stub,
                direct_mode=True,
                force_local_tts=force_local_tts,
                music_only_background=music_only_background,
            )
            return translation

        # SPLIT MODE: First, get segments without TTS
        base_translation = await self.translation_service.direct_localize_video(  # type: ignore
            video.file_path,
            country,
            force_local_tts=False,
            music_only_background=music_only_background,
            skip_tts=True,
        )

        segments = base_translation.segments or []
        if not segments:
            return base_translation

        # Compute split
        parts: List[List] = []
        if max_part_duration and max_part_duration > 0:
            current = []
            acc = 0.0
            for seg in segments:
                dur = float(seg.end_time) - float(seg.start_time)
                if current and acc + dur > max_part_duration:
                    parts.append(current)
                    current = []
                    acc = 0.0
                current.append(seg)
                acc += dur
            if current:
                parts.append(current)
        elif split_into_parts and split_into_parts > 1:
            size = max(1, int(round(len(segments) / split_into_parts)))
            for i in range(0, len(segments), size):
                parts.append(segments[i:i+size])
        else:
            parts = [segments]

        # Render each part as separate video
        rendered_paths = []
        rendered_urls = []
        from core.config.settings import settings
        for idx, part in enumerate(parts, start=1):
            try:
                part_translation = await self.translation_service.direct_localize_video(  # type: ignore
                    video.file_path,
                    country,
                    force_local_tts=force_local_tts,
                    music_only_background=music_only_background,
                    precomputed_segments=part,
                    precomputed_duration=base_translation.video_duration,
                    output_suffix=f"part{idx}",
                )
                if part_translation.final_video_path:
                    import os
                    filename = os.path.basename(part_translation.final_video_path)
                    rendered_paths.append(part_translation.final_video_path)
                    rendered_urls.append(f"/api/localization/download/{filename}")
            except Exception as e:
                logger.error(f"Failed to render part {idx}: {e}")

        # Update base translation to carry first part path and store auxiliary info
        if rendered_paths:
            base_translation.final_video_path = rendered_paths[0]
        # Store parts info in warnings or extra (no dedicated field in entity)
        base_translation.warnings = base_translation.warnings or []
        base_translation.warnings.append(
            {
                "parts": [
                    {"index": i+1, "final_video_url": rendered_urls[i], "final_video_path": rendered_paths[i]}
                    for i in range(len(rendered_paths))
                ]
            }
        )

        # Persist/update translation record
        base_translation.country_id = country.id
        existing = await self.translation_repository.get_by_video_and_country(video.id, country.id)
        if existing:
            base_translation.id = existing.id
            base_translation.status = existing.status
            await self.translation_repository.update(base_translation)
            return await self.translation_repository.get_by_id(existing.id)
        else:
            created = await self.translation_repository.create(base_translation)
            return created

    async def _ensure_transcribed(self, video: Video) -> Transcription:
        """Ensure video is transcribed, create transcription if needed"""
        transcription = await self.transcription_repository.get_by_video_id(video.id)

        if not transcription or transcription.status != "completed":
            # Video needs to be transcribed
            # This would typically call the transcription service
            # For now, we'll raise an error if not transcribed
            raise Exception(f"Video {video.id} is not transcribed. Please transcribe first.")

        return transcription

    async def _ensure_pseudo_transcription(self, video: Video) -> Transcription:
        """Ensure there is at least a placeholder transcription row for direct mode."""
        transcription = await self.transcription_repository.get_by_video_id(video.id)
        if transcription:
            return transcription

        from domain.entities.transcription import Transcription, TranscriptionStatus
        pseudo = Transcription(
            video_id=video.id,
            status=TranscriptionStatus.COMPLETED,
            language_code=video.language or "auto",
            full_text=None,
            segments=[],
            confidence_score=None,
            processing_time=0.0,
            model_used="direct-localization",
            extra_metadata={"note": "placeholder for direct localization"}
        )
        return await self.transcription_repository.create(pseudo)

    async def _process_single_translation(
        self,
        video: Video,
        transcription: Transcription,
        country: Country,
        job: LocalizationJob,
        direct_mode: bool = True,
        **kwargs
    ) -> Translation:
        """Process translation for a single country"""
        try:
            logger.info(f"Starting translation for {country.country_code} - {country.country_name}")

            # Check if translation already exists
            existing = await self.translation_repository.get_by_video_and_country(
                video.id, country.id
            )

            if existing and existing.status == TranslationStatus.COMPLETED:
                logger.info(f"Translation already exists for video {video.id}, country {country.country_code}")
                return existing

            # Reuse existing record if present; otherwise create
            if existing:
                translation = existing
                translation.status = TranslationStatus.PENDING
                translation.error_message = None
                translation.warnings = []
                await self.translation_repository.update(translation)
            else:
                translation = Translation(
                    video_id=video.id,
                    transcription_id=transcription.id,
                    country_id=country.id,
                    source_language=transcription.language_code,
                    target_language=country.language_code,
                    country_code=country.country_code,
                    status=TranslationStatus.PENDING
                )
                translation = await self.translation_repository.create(translation)

            if direct_mode:
                # Direct localization using video-only context
                try:
                    updated_translation = await self.translation_service.direct_localize_video(
                        video.file_path,
                        country,
                        **kwargs,
                    )
                except TypeError:
                    # Older implementation without kwargs
                    updated_translation = await self.translation_service.direct_localize_video(
                        video.file_path,
                        country,
                    )
            else:
                # Analyze video context + translate using transcript text
                video_analysis = await self.translation_service.analyze_video_context(
                    video.file_path,
                    transcription.full_text or "",
                    country
                )
                updated_translation = await self.translation_service.translate_with_context(
                    video.file_path,
                    transcription.full_text or "",
                    country,
                    video_analysis
                )

            # Update translation in database
            updated_translation.id = translation.id
            translation = await self.translation_repository.update(updated_translation)

            return translation

        except Exception as e:
            logger.error(f"Single translation processing failed: {str(e)}")
            # Update translation status to failed if it exists
            if 'translation' in locals():
                translation.status = TranslationStatus.FAILED
                translation.error_message = str(e)
                await self.translation_repository.update(translation)
                return translation
            raise

    async def _extract_video_audio(self, video_path: str) -> Optional[str]:
        """Extract audio track from video file"""
        try:
            import subprocess
            import tempfile
            from pathlib import Path

            # Create temporary audio file
            temp_dir = Path(self.audio_mixing_service.temp_dir)
            audio_path = temp_dir / f"extracted_audio_{int(asyncio.get_event_loop().time())}.wav"

            # Extract audio using FFmpeg
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # Uncompressed audio
                "-ar", "44100",  # Sample rate
                "-ac", "2",  # Stereo
                str(audio_path)
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0 and audio_path.exists():
                logger.info(f"Extracted audio from video: {audio_path}")
                return str(audio_path)
            else:
                logger.error(f"Audio extraction failed: {stderr.decode()}")
                return None

        except Exception as e:
            logger.error(f"Video audio extraction failed: {str(e)}")
            return None

    async def _generate_voice_segments_standard(
        self,
        segments: List,
        country: Country,
        country_code: str
    ) -> List[Dict[str, Any]]:
        """Generate voice segments using standard TTS services"""
        try:
            voice_segments = []

            # Use ElevenLabs if available, otherwise fallback
            if self.elevenlabs_service:
                temp_segments = await self.elevenlabs_service.generate_speech_for_segments(
                    segments,
                    country.language_code,
                    country_code,
                    str(self.audio_mixing_service.temp_dir)
                )
                voice_segments.extend(temp_segments)

            return voice_segments

        except Exception as e:
            logger.error(f"Standard voice generation failed: {str(e)}")
            return []

    async def _create_final_mixed_audio(
        self,
        voice_segments: List[Dict[str, Any]],
        separated_audio: Optional[Dict[str, str]],
        original_audio_path: str,
        total_duration: float,
        preserve_background: bool,
        background_volume: float,
        voice_volume: float,
        audio_quality: str
    ) -> Optional[str]:
        """Create final mixed audio track"""
        try:
            # Create mixing configuration
            config = AudioMixConfig(
                voice_volume=voice_volume,
                background_volume=background_volume,
                normalize_audio=True,
                output_format="wav" if audio_quality == "high" else "mp3",
                sample_rate=44100 if audio_quality == "high" else 22050
            )

            output_path = self.audio_mixing_service.temp_dir / f"final_mixed_{int(asyncio.get_event_loop().time())}.{config.output_format}"

            if preserve_background and separated_audio and "accompaniment" in separated_audio:
                # Mix with preserved background music
                result = await self.audio_mixing_service.mix_segmented_voice_with_background(
                    voice_segments=voice_segments,
                    background_audio_path=separated_audio["accompaniment"],
                    output_path=str(output_path),
                    total_duration=total_duration,
                    config=config
                )
            else:
                # Mix voice segments only (no background preservation)
                result = await self.audio_mixing_service.mix_segmented_voice_with_background(
                    voice_segments=voice_segments,
                    background_audio_path=original_audio_path,
                    output_path=str(output_path),
                    total_duration=total_duration,
                    config=AudioMixConfig(
                        voice_volume=voice_volume,
                        background_volume=0.05,  # Very low background
                        **config.__dict__
                    )
                )

            return result

        except Exception as e:
            logger.error(f"Final audio mixing failed: {str(e)}")
            return None

    async def _create_final_video_with_audio(
        self,
        original_video_path: str,
        mixed_audio_path: str,
        video_id: int,
        country_code: str
    ) -> Optional[str]:
        """Create final video with mixed audio track"""
        try:
            import subprocess
            from pathlib import Path

            # Generate output filename
            video_filename = Path(original_video_path).stem
            output_filename = f"{video_filename}_{country_code}_enhanced_{int(asyncio.get_event_loop().time())}.mp4"
            output_path = self.audio_mixing_service.output_dir / output_filename

            # Replace audio in video using FFmpeg
            cmd = [
                "ffmpeg", "-y",
                "-i", original_video_path,  # Video input
                "-i", mixed_audio_path,     # Audio input
                "-c:v", "copy",             # Copy video stream
                "-c:a", "aac",              # Encode audio as AAC
                "-b:a", "192k",             # Audio bitrate
                "-map", "0:v:0",            # Map video from first input
                "-map", "1:a:0",            # Map audio from second input
                "-shortest",                # End when shortest stream ends
                str(output_path)
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0 and output_path.exists():
                logger.info(f"Created final video with enhanced audio: {output_path}")
                return str(output_path)
            else:
                logger.error(f"Final video creation failed: {stderr.decode()}")
                return None

        except Exception as e:
            logger.error(f"Final video creation failed: {str(e)}")
            return None

    async def analyze_audio_separation_feasibility(self, video_id: int) -> Dict[str, Any]:
        """
        Analyze whether a video is suitable for audio separation

        Args:
            video_id: ID of the video to analyze

        Returns:
            Analysis results with recommendations
        """
        try:
            video = await self.video_repository.get_by_id(video_id)
            if not video:
                return {"error": "Video not found"}

            # Extract audio for analysis
            audio_path = await self._extract_video_audio(video.file_path)
            if not audio_path:
                return {"error": "Could not extract audio for analysis"}

            # Analyze separation feasibility
            separation_info = await self.audio_separation_service.get_separation_info(audio_path)

            # Add video-specific recommendations
            recommendations = []
            if separation_info.get("separation_feasible"):
                recommendations.append("✓ Audio separation is feasible - stereo audio detected")
                recommendations.append("✓ Background music preservation recommended")

                if separation_info.get("expected_quality") == "high":
                    recommendations.append("✓ High-quality separation expected")
                else:
                    recommendations.append("⚠ Medium-quality separation expected")
            else:
                recommendations.append("⚠ Audio separation may not be effective - mono audio or insufficient channels")
                recommendations.append("• Consider using standard localization without background preservation")

            # Add duration-based recommendations
            duration = separation_info.get("duration", 0)
            if duration > 300:  # 5 minutes
                recommendations.append("⚠ Long video detected - consider splitting for better performance")

            return {
                **separation_info,
                "recommendations": recommendations,
                "enhanced_localization_recommended": separation_info.get("separation_feasible", False)
            }

        except Exception as e:
            logger.error(f"Audio separation analysis failed: {str(e)}")
            return {"error": str(e)}

    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up temporary audio processing files"""
        try:
            self.audio_separation_service.cleanup_temp_files(max_age_hours)
            self.audio_mixing_service.cleanup_temp_files(max_age_hours)
            logger.info("Audio processing temp files cleaned up")
        except Exception as e:
            logger.error(f"Temp file cleanup failed: {str(e)}")
