import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from domain.entities.video import Video
from domain.entities.country import Country
from domain.entities.translation import Translation, TranslationJob
from domain.entities.localization_job import LocalizationJob

from domain.repositories.video_repository import VideoRepository
from domain.repositories.country_repository import CountryRepository
from domain.repositories.translation_repository import TranslationRepository
from domain.repositories.localization_job_repository import LocalizationJobRepository

from application.services.localization_service import LocalizationService

logger = logging.getLogger(__name__)


class LocalizationUseCases:
    """Business logic for video localization operations"""

    def __init__(
        self,
        video_repository: VideoRepository,
        country_repository: CountryRepository,
        translation_repository: TranslationRepository,
        localization_job_repository: LocalizationJobRepository,
        localization_service: LocalizationService
    ):
        self.video_repository = video_repository
        self.country_repository = country_repository
        self.translation_repository = translation_repository
        self.localization_job_repository = localization_job_repository
        self.localization_service = localization_service

    async def get_available_countries_for_localization(
        self,
        group_by_language: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get available countries for localization, optionally grouped by language

        Args:
            group_by_language: Whether to group countries by language

        Returns:
            List of country data or language-grouped data
        """
        try:
            countries = await self.localization_service.get_available_countries()

            if not group_by_language:
                return [
                    {
                        "id": country.id,
                        "country_code": country.country_code,
                        "country_name": country.country_name,
                        "language_code": country.language_code,
                        "language_name": country.language_name,
                        "dialect": country.dialect_info.primary_dialect,
                        "communication_style": country.cultural_context.communication_style,
                        "marketing_preferences": country.cultural_context.marketing_preferences,
                        "priority": country.priority
                    }
                    for country in sorted(countries, key=lambda x: (x.priority, x.country_name))
                ]

            # Group by language
            language_groups = {}
            for country in countries:
                if country.language_code not in language_groups:
                    language_groups[country.language_code] = {
                        "language_code": country.language_code,
                        "language_name": country.language_name,
                        "countries": []
                    }

                language_groups[country.language_code]["countries"].append({
                    "id": country.id,
                    "country_code": country.country_code,
                    "country_name": country.country_name,
                    "language_code": country.language_code,
                    "language_name": country.language_name,
                    "dialect": country.dialect_info.primary_dialect,
                    "communication_style": country.cultural_context.communication_style,
                    "marketing_preferences": country.cultural_context.marketing_preferences,
                    "priority": country.priority
                })

            return list(language_groups.values())

        except Exception as e:
            logger.error(f"Failed to get available countries: {str(e)}")
            raise

    async def create_localization_request(
        self,
        video_id: int,
        target_countries: List[str],
        user_id: Optional[int] = None,
        preferences: Optional[Dict[str, Any]] = None
    ) -> LocalizationJob:
        """
        Create a new localization request for a video

        Args:
            video_id: ID of the video to localize
            target_countries: List of country codes to localize for
            user_id: Optional user ID making the request
            preferences: Optional localization preferences

        Returns:
            Created LocalizationJob

        Raises:
            ValueError: If validation fails
        """
        try:
            # Validate video exists and is ready for localization
            video = await self.video_repository.get_by_id(video_id)
            if not video:
                raise ValueError("Video not found")

            if video.status not in ["transcribed", "translated", "localized", "completed"]:
                raise ValueError("Video must be transcribed before localization")

            # Validate target countries
            if not target_countries:
                raise ValueError("At least one target country must be specified")

            # Check for duplicates
            if len(target_countries) != len(set(target_countries)):
                raise ValueError("Duplicate country codes found")

            # Validate country codes exist
            valid_countries = await self.country_repository.get_by_country_codes(target_countries)
            valid_codes = [c.country_code for c in valid_countries]
            invalid_codes = [code for code in target_countries if code not in valid_codes]

            if invalid_codes:
                raise ValueError(f"Invalid country codes: {invalid_codes}")

            # Set default preferences
            default_preferences = {
                "analysis_depth": "comprehensive",
                "cultural_sensitivity": "high",
                "brand_consistency": "strict",
                "preserve_brand_elements": True,
                "adapt_for_culture": True,
                "maintain_video_timing": True
            }

            if preferences:
                default_preferences.update(preferences)

            # Create localization job
            job = await self.localization_service.create_localization_job(
                video_id=video_id,
                target_country_codes=target_countries,
                user_id=user_id,
                config=default_preferences
            )

            logger.info(f"Created localization request {job.id} for video {video_id}")
            return job

        except Exception as e:
            logger.error(f"Failed to create localization request: {str(e)}")
            raise

    async def start_localization_process(self, job_id: int) -> Dict[str, Any]:
        """
        Start the localization process for a job

        Args:
            job_id: ID of the localization job

        Returns:
            Job status information
        """
        try:
            # Process the localization job (this runs the full pipeline)
            job = await self.localization_service.process_localization_job(job_id)

            # Get fresh status details to compute counts
            status = await self.localization_service.get_localization_job_status(job.id)

            return {
                "job_id": job.id,
                "status": job.status,
                "progress": job.progress_percentage,
                "success_count": status.get("success_count", 0),
                "failure_count": status.get("failure_count", 0),
                "estimated_completion": job.estimated_completion,
                "translations_created": job.translation_ids
            }

        except Exception as e:
            logger.error(f"Failed to start localization process: {str(e)}")
            raise

    async def get_localization_job_details(self, job_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a localization job

        Args:
            job_id: ID of the localization job

        Returns:
            Detailed job information
        """
        try:
            status = await self.localization_service.get_localization_job_status(job_id)

            # Enhance with additional business logic
            job = await self.localization_job_repository.get_by_id(job_id)
            video = await self.video_repository.get_by_id(job.video_id)

            enhanced_status = {
                **status,
                "video_info": {
                    "id": video.id,
                    "filename": video.original_filename,
                    "duration": video.duration,
                    "language": video.language
                } if video else None,
                "cost_estimate": self._calculate_cost_estimate(job),
                "quality_metrics": await self._calculate_quality_metrics(job_id)
            }

            return enhanced_status

        except Exception as e:
            logger.error(f"Failed to get localization job details: {str(e)}")
            raise

    async def get_translation_result(
        self,
        translation_id: int,
        include_analysis: bool = False
    ) -> Dict[str, Any]:
        """
        Get translation result with optional detailed analysis

        Args:
            translation_id: ID of the translation
            include_analysis: Whether to include detailed analysis

        Returns:
            Translation result data
        """
        try:
            translation = await self.localization_service.get_translation_by_id(translation_id)
            if not translation:
                raise ValueError("Translation not found")

            # Get country information
            country = await self.country_repository.get_by_id(translation.country_id)

            result = {
                "translation_id": translation.id,
                "status": translation.status,
                "target_country": {
                    "code": country.country_code,
                    "name": country.country_name,
                    "language": country.language_name
                } if country else None,
                "translated_text": translation.full_translated_text,
                "confidence_score": translation.overall_confidence,
                "cultural_appropriateness": translation.cultural_appropriateness_score,
                "effectiveness_prediction": translation.effectiveness_prediction,
                "processing_time": translation.processing_time,
                "segments": [
                    {
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "original_text": seg.original_text,
                        "translated_text": seg.translated_text,
                        "confidence": seg.confidence_score,
                        "cultural_adaptations": seg.cultural_adaptations
                    }
                    for seg in translation.segments
                ] if translation.segments else [],
                "warnings": translation.warnings
            }

            if include_analysis:
                result.update({
                    "video_analysis": translation.video_analysis,
                    "cultural_adaptation": {
                        "original_concept": translation.cultural_adaptation.original_concept,
                        "adapted_concept": translation.cultural_adaptation.adapted_concept,
                        "changes_made": translation.cultural_adaptation.changes_made,
                        "cultural_reasoning": translation.cultural_adaptation.cultural_reasoning,
                        "effectiveness_score": translation.cultural_adaptation.effectiveness_score
                    } if translation.cultural_adaptation else None,
                    "advertising_context": translation.advertising_context
                })

            return result

        except Exception as e:
            logger.error(f"Failed to get translation result: {str(e)}")
            raise

    async def get_video_localizations(self, video_id: int) -> Dict[str, Any]:
        """
        Get all localizations for a specific video

        Args:
            video_id: ID of the video

        Returns:
            Summary of all localizations for the video
        """
        try:
            # Get video info
            video = await self.video_repository.get_by_id(video_id)
            if not video:
                raise ValueError("Video not found")

            # Get all translations for this video
            translations = await self.localization_service.get_translations_for_video(video_id)

            # Get localization jobs for this video
            jobs = await self.localization_job_repository.get_by_video_id(video_id)

            # Organize translations by country
            translations_by_country = {}
            for translation in translations:
                country = await self.country_repository.get_by_id(translation.country_id)
                if country:
                    translations_by_country[country.country_code] = {
                        "translation_id": translation.id,
                        "country_name": country.country_name,
                        "language_name": country.language_name,
                        "status": translation.status,
                        "confidence": translation.overall_confidence,
                        "cultural_score": translation.cultural_appropriateness_score,
                        "effectiveness": translation.effectiveness_prediction,
                        "created_at": translation.created_at
                    }

            return {
                "video_id": video_id,
                "video_info": {
                    "filename": video.original_filename,
                    "duration": video.duration,
                    "original_language": video.language,
                    "status": video.status
                },
                "localization_summary": {
                    "total_countries": len(translations_by_country),
                    "completed_translations": len([t for t in translations if t.status == "completed"]),
                    "in_progress_translations": len([t for t in translations if t.status in ["pending", "analyzing_context", "translating", "cultural_adaptation"]]),
                    "failed_translations": len([t for t in translations if t.status == "failed"])
                },
                "translations_by_country": translations_by_country,
                "localization_jobs": [
                    {
                        "job_id": job.id,
                        "status": job.status,
                        "progress": job.progress_percentage,
                        "created_at": job.created_at
                    }
                    for job in jobs
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get video localizations: {str(e)}")
            raise

    async def retry_failed_localization(self, translation_id: int) -> Dict[str, Any]:
        """
        Retry a failed translation

        Args:
            translation_id: ID of the failed translation

        Returns:
            Updated translation status
        """
        try:
            translation = await self.localization_service.retry_failed_translation(translation_id)

            return {
                "translation_id": translation.id,
                "status": translation.status,
                "country_code": translation.country_code,
                "retry_initiated_at": datetime.utcnow(),
                "previous_errors": translation.error_message
            }

        except Exception as e:
            logger.error(f"Failed to retry localization: {str(e)}")
            raise

    async def cancel_localization_job(self, job_id: int) -> Dict[str, Any]:
        """
        Cancel a localization job (if still in progress)

        Args:
            job_id: ID of the job to cancel

        Returns:
            Cancellation status
        """
        try:
            job = await self.localization_job_repository.get_by_id(job_id)
            if not job:
                raise ValueError("Job not found")

            if job.status in ["completed", "failed"]:
                raise ValueError(f"Cannot cancel job in {job.status} status")

            # Update job status to cancelled
            job.status = "cancelled"
            await self.localization_job_repository.update(job)

            return {
                "job_id": job_id,
                "status": "cancelled",
                "cancelled_at": datetime.utcnow(),
                "progress_when_cancelled": job.progress_percentage
            }

        except Exception as e:
            logger.error(f"Failed to cancel localization job: {str(e)}")
            raise

    def _calculate_cost_estimate(self, job: LocalizationJob) -> Dict[str, Any]:
        """Calculate cost estimate for localization job"""
        # Basic cost calculation - in production this would be more sophisticated
        base_cost_per_country = 50.0  # Base cost in USD

        # Read optional attributes with sensible defaults (older jobs may not have these fields)
        analysis_depth = getattr(job, "analysis_depth", "comprehensive")
        cultural_sensitivity = getattr(job, "cultural_sensitivity", "high")
        target_countries = getattr(job, "target_countries", []) or []

        complexity_multiplier = {
            "basic": 1.0,
            "standard": 1.5,
            "comprehensive": 2.0
        }.get(analysis_depth, 1.5)

        cultural_multiplier = {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5
        }.get(cultural_sensitivity, 1.2)

        total_cost = len(target_countries) * base_cost_per_country * complexity_multiplier * cultural_multiplier

        return {
            "estimated_cost_usd": round(total_cost, 2),
            "cost_per_country": round(total_cost / max(len(target_countries), 1), 2),
            "factors": {
                "base_cost": base_cost_per_country,
                "complexity_multiplier": complexity_multiplier,
                "cultural_multiplier": cultural_multiplier,
                "number_of_countries": len(target_countries)
            }
        }

    async def _calculate_quality_metrics(self, job_id: int) -> Dict[str, Any]:
        """Calculate quality metrics for completed translations"""
        try:
            job = await self.localization_job_repository.get_by_id(job_id)
            if not job or not job.translation_ids:
                return {}

            # Get all translations for this job
            confidences = []
            cultural_scores = []
            effectiveness_scores = []

            for translation_id in job.translation_ids:
                translation = await self.translation_repository.get_by_id(translation_id)
                if translation and translation.status == "completed":
                    if translation.overall_confidence:
                        confidences.append(translation.overall_confidence)
                    if translation.cultural_appropriateness_score:
                        cultural_scores.append(translation.cultural_appropriateness_score)
                    if translation.effectiveness_prediction:
                        effectiveness_scores.append(translation.effectiveness_prediction)

            return {
                "average_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
                "average_cultural_score": round(sum(cultural_scores) / len(cultural_scores), 3) if cultural_scores else 0,
                "average_effectiveness": round(sum(effectiveness_scores) / len(effectiveness_scores), 3) if effectiveness_scores else 0,
                "completed_translations": len(confidences),
                "total_translations": len(job.translation_ids)
            }

        except Exception as e:
            logger.warning(f"Failed to calculate quality metrics: {str(e)}")
            return {}
