from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from domain.entities.translation import Translation, TranslationJob, VideoSceneContext
from domain.entities.country import Country


class TranslationService(ABC):
    """Abstract base class for translation services with video context awareness"""

    @abstractmethod
    async def analyze_video_context(
        self,
        video_path: str,
        transcription_text: str,
        target_country: Country
    ) -> Dict[str, Any]:
        """
        Analyze video content holistically including visual and audio elements

        Args:
            video_path: Path to the video file
            transcription_text: Transcribed text from the video
            target_country: Target country for cultural context

        Returns:
            Dictionary containing comprehensive video analysis
        """
        pass

    @abstractmethod
    async def translate_with_context(
        self,
        video_path: str,
        transcription: str,
        target_country: Country,
        video_analysis: Dict[str, Any]
    ) -> Translation:
        """
        Translate content with full video and cultural context awareness

        Args:
            video_path: Path to the video file
            transcription: Original transcription text
            target_country: Target country with cultural context
            video_analysis: Result from analyze_video_context

        Returns:
            Translation object with culturally adapted content
        """
        pass

    @abstractmethod
    async def extract_video_scenes(
        self,
        video_path: str,
        interval_seconds: float = 5.0
    ) -> List[VideoSceneContext]:
        """
        Extract scene contexts from video at regular intervals

        Args:
            video_path: Path to the video file
            interval_seconds: How often to sample scenes

        Returns:
            List of VideoSceneContext objects
        """
        pass

    @abstractmethod
    async def assess_cultural_appropriateness(
        self,
        translation: Translation,
        target_country: Country,
        video_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess cultural appropriateness of the translation

        Args:
            translation: Translation to assess
            target_country: Target country context
            video_analysis: Video analysis results

        Returns:
            Assessment results with scores and recommendations
        """
        pass

    @abstractmethod
    async def optimize_for_advertising_effectiveness(
        self,
        translation: Translation,
        target_country: Country,
        original_intent: Dict[str, Any]
    ) -> Translation:
        """
        Optimize translation to maintain advertising effectiveness

        Args:
            translation: Initial translation
            target_country: Target country context
            original_intent: Original advertising intent analysis

        Returns:
            Optimized translation
        """
        pass