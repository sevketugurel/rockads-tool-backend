from abc import ABC, abstractmethod
from typing import Optional, List
from domain.entities.transcription import Transcription, TranscriptionSegment


class TranscriptionService(ABC):
    """Abstract base class for transcription services"""

    @abstractmethod
    async def transcribe_video(self, video_path: str, language_hint: Optional[str] = None) -> Transcription:
        """
        Transcribe video to text using AI service

        Args:
            video_path: Path to the video file
            language_hint: Optional language hint for better accuracy

        Returns:
            Transcription object with text and metadata
        """
        pass

    @abstractmethod
    async def extract_audio(self, video_path: str, output_path: str) -> bool:
        """
        Extract audio from video file

        Args:
            video_path: Path to the video file
            output_path: Path where audio should be saved

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def detect_language(self, text: str) -> str:
        """
        Detect language from text

        Args:
            text: Text to analyze

        Returns:
            ISO 639-1 language code
        """
        pass