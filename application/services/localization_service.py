import asyncio
import logging
from typing import List, Dict, Any, Optional
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

    async def process_localization_job(self, job_id: int) -> LocalizationJob:
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
            job.status = LocalizationJobStatus.TRANSCRIBING
            await self.localization_job_repository.update(job)

            # Get video and ensure it's transcribed
            video = await self.video_repository.get_by_id(job.video_id)
            transcription = await self._ensure_transcribed(video)

            if not transcription or transcription.status != "completed":
                raise Exception("Video transcription failed or incomplete")

            # Update job status
            job.status = LocalizationJobStatus.TRANSLATING
            job.transcription_id = transcription.id
            await self.localization_job_repository.update(job)

            # Process translations for each target country
            translations: List[int] = []
            total_countries = len(job.target_countries or [])

            # Track counts locally to avoid relying on DB columns
            success_count = 0
            failure_count = 0

            for i, country_id in enumerate(job.target_countries or []):
                try:
                    logger.info(f"Processing translation {i+1}/{total_countries} for country {country_id}")

                    # Get country details
                    country = await self.country_repository.get_by_id(country_id)
                    if not country:
                        logger.warning(f"Country {country_id} not found, skipping")
                        failure_count += 1
                        continue

                    # Create and process translation
                    translation = await self._process_single_translation(
                        video, transcription, country, job
                    )

                    if translation.status == TranslationStatus.COMPLETED:
                        translations.append(translation.id)
                        success_count += 1
                    else:
                        failure_count += 1

                    # Update progress
                    job.progress_percentage = ((i + 1) / total_countries) * 100
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
                        "effectiveness": translation.effectiveness_prediction
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
            video, transcription, country, job_config
        )

        return updated_translation

    async def _ensure_transcribed(self, video: Video) -> Transcription:
        """Ensure video is transcribed, create transcription if needed"""
        transcription = await self.transcription_repository.get_by_video_id(video.id)

        if not transcription or transcription.status != "completed":
            # Video needs to be transcribed
            # This would typically call the transcription service
            # For now, we'll raise an error if not transcribed
            raise Exception(f"Video {video.id} is not transcribed. Please transcribe first.")

        return transcription

    async def _process_single_translation(
        self,
        video: Video,
        transcription: Transcription,
        country: Country,
        job: LocalizationJob
    ) -> Translation:
        """Process translation for a single country"""
        try:
            # Check if translation already exists
            existing = await self.translation_repository.get_by_video_and_country(
                video.id, country.id
            )

            if existing and existing.status == TranslationStatus.COMPLETED:
                logger.info(f"Translation already exists for video {video.id}, country {country.country_code}")
                return existing

            # Create new translation record
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

            # Analyze video context
            video_analysis = await self.translation_service.analyze_video_context(
                video.file_path,
                transcription.full_text,
                country
            )

            # Perform context-aware translation
            updated_translation = await self.translation_service.translate_with_context(
                video.file_path,
                transcription.full_text,
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
