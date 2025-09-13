import os
import asyncio
import tempfile
import time
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

import google.generativeai as genai
from moviepy.editor import VideoFileClip
from PIL import Image

from application.services.ai.transcription_service import TranscriptionService
from domain.entities.transcription import (
    Transcription,
    TranscriptionSegment,
    TranscriptionStatus
)
from core.config.settings import settings

logger = logging.getLogger(__name__)


class GeminiTranscriptionService(TranscriptionService):
    """Google Gemini implementation of transcription service"""

    def __init__(self):
        """Initialize Gemini client"""
        if not settings.gemini_api_key or settings.gemini_api_key == "your-gemini-api-key-here":
            raise ValueError("Gemini API key not configured. Please set GEMINI_API_KEY in your .env file")

        # Configure with global region to avoid regional limits
        genai.configure(
            api_key=settings.gemini_api_key,
            transport="rest"  # Use REST instead of gRPC for better global availability
        )
        self.model = genai.GenerativeModel(settings.gemini_model)

    async def transcribe_video(self, video_path: str, language_hint: Optional[str] = None) -> Transcription:
        """
        Transcribe video using Google Gemini 2.5 Pro

        Args:
            video_path: Path to the video file
            language_hint: Optional language hint for better accuracy

        Returns:
            Transcription object with text and metadata
        """
        start_time = time.time()

        try:
            logger.info(f"Starting transcription for video: {video_path}")

            # Create transcription object
            transcription = Transcription(
                video_id=0,  # Will be set by the calling code
                status=TranscriptionStatus.PROCESSING,
                language_code=language_hint or "auto",
                model_used=settings.gemini_model
            )

            # Upload video to Gemini
            logger.info("Uploading video to Gemini...")
            video_file = genai.upload_file(path=video_path)

            # Wait for video to be processed
            while video_file.state.name == "PROCESSING":
                logger.info("Video is processing...")
                await asyncio.sleep(5)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED":
                raise Exception(f"Video processing failed: {video_file.state}")

            # Create prompt for transcription with advertisement context
            prompt = self._create_transcription_prompt(language_hint)

            logger.info("Generating transcription...")

            # Generate transcription
            # Add delay to respect rate limits
            await asyncio.sleep(2)  # 2 second delay between requests
            response = self.model.generate_content([video_file, prompt])

            if not response.text:
                raise Exception("No transcription generated")

            # Parse the response
            full_text, segments = self._parse_gemini_response(response.text)

            # Detect language if not provided
            if language_hint is None or language_hint == "auto":
                detected_language = self.detect_language(full_text)
                transcription.language_code = detected_language

            # Update transcription with results
            transcription.full_text = full_text
            transcription.segments = segments
            transcription.status = TranscriptionStatus.COMPLETED
            transcription.processing_time = time.time() - start_time
            transcription.confidence_score = self._calculate_confidence_score(response)
            transcription.extra_metadata = {
                "gemini_model": settings.gemini_model,
                "video_duration": self._get_video_duration(video_path),
                "file_size": os.path.getsize(video_path)
            }

            # Clean up uploaded file
            genai.delete_file(video_file.name)

            logger.info(f"Transcription completed in {transcription.processing_time:.2f} seconds")
            return transcription

        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            transcription.status = TranscriptionStatus.FAILED
            transcription.error_message = str(e)
            transcription.processing_time = time.time() - start_time
            return transcription

    async def extract_audio(self, video_path: str, output_path: str) -> bool:
        """
        Extract audio from video file using moviepy

        Args:
            video_path: Path to the video file
            output_path: Path where audio should be saved

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Extracting audio from {video_path} to {output_path}")

            # Load video and extract audio
            video = VideoFileClip(video_path)
            audio = video.audio

            # Save audio as WAV file
            audio.write_audiofile(output_path, verbose=False, logger=None)

            # Clean up
            audio.close()
            video.close()

            logger.info("Audio extraction completed successfully")
            return True

        except Exception as e:
            logger.error(f"Audio extraction failed: {str(e)}")
            return False

    def detect_language(self, text: str) -> str:
        """
        Detect language from text using simple heuristics
        Note: In production, you might want to use a dedicated language detection library

        Args:
            text: Text to analyze

        Returns:
            ISO 639-1 language code
        """
        if not text:
            return "en"

        # Simple language detection based on common words
        # This is a basic implementation - consider using langdetect or similar library
        turkish_words = ["ve", "bir", "bu", "için", "ile", "olan", "en", "var", "gibi"]
        spanish_words = ["el", "la", "de", "que", "y", "en", "un", "es", "se", "no"]
        german_words = ["der", "die", "und", "in", "den", "von", "zu", "das", "mit", "sich"]
        french_words = ["le", "de", "et", "à", "un", "il", "être", "et", "en", "avoir"]

        text_lower = text.lower()

        # Count occurrences of language-specific words
        turkish_count = sum(1 for word in turkish_words if word in text_lower)
        spanish_count = sum(1 for word in spanish_words if word in text_lower)
        german_count = sum(1 for word in german_words if word in text_lower)
        french_count = sum(1 for word in french_words if word in text_lower)

        # Find the language with highest count
        language_scores = {
            "tr": turkish_count,
            "es": spanish_count,
            "de": german_count,
            "fr": french_count
        }

        detected = max(language_scores, key=language_scores.get)

        # If no clear winner or very low counts, default to English
        if language_scores[detected] < 2:
            detected = "en"

        logger.info(f"Detected language: {detected}")
        return detected

    def _create_transcription_prompt(self, language_hint: Optional[str] = None) -> str:
        """Create prompt for Gemini transcription with advertisement context"""

        base_prompt = """
        Please transcribe the speech from this video with high accuracy. This video contains advertising/marketing content, so pay special attention to:

        1. Brand names and product names (maintain exact spelling)
        2. Marketing slogans and catchphrases
        3. Call-to-action phrases
        4. Numbers, prices, and statistics
        5. Technical terms related to the product/service

        Please provide the transcription in the following format:
        - Include timestamps if possible (format: [MM:SS] text)
        - Maintain proper punctuation and capitalization
        - Preserve the exact wording of brand names and marketing terms
        - If multiple speakers are present, indicate speaker changes

        Return only the transcription text with timestamps.
        """

        if language_hint and language_hint != "auto":
            base_prompt += f"\n\nThe primary language of this video is: {language_hint}"

        return base_prompt

    def _parse_gemini_response(self, response_text: str) -> tuple[str, List[TranscriptionSegment]]:
        """
        Parse Gemini response to extract text and segments

        Args:
            response_text: Raw response from Gemini

        Returns:
            Tuple of (full_text, segments_list)
        """
        segments = []
        lines = response_text.strip().split('\n')
        full_text_parts = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Try to parse timestamp format [MM:SS] or [HH:MM:SS]
            if line.startswith('[') and ']' in line:
                try:
                    timestamp_end = line.index(']')
                    timestamp_str = line[1:timestamp_end]
                    text = line[timestamp_end + 1:].strip()

                    # Parse timestamp to seconds
                    time_parts = timestamp_str.split(':')
                    if len(time_parts) == 2:  # MM:SS
                        minutes, seconds = map(int, time_parts)
                        start_seconds = minutes * 60 + seconds
                    elif len(time_parts) == 3:  # HH:MM:SS
                        hours, minutes, seconds = map(int, time_parts)
                        start_seconds = hours * 3600 + minutes * 60 + seconds
                    else:
                        start_seconds = 0

                    if text:
                        segment = TranscriptionSegment(
                            start_time=start_seconds,
                            end_time=start_seconds + 5,  # Estimate 5 seconds duration
                            text=text,
                            confidence=0.9  # Default confidence
                        )
                        segments.append(segment)
                        full_text_parts.append(text)

                except (ValueError, IndexError):
                    # If timestamp parsing fails, treat as regular text
                    full_text_parts.append(line)
            else:
                # No timestamp, add to full text
                full_text_parts.append(line)

        full_text = ' '.join(full_text_parts)

        # If no segments were created, create one segment with all text
        if not segments and full_text:
            segments = [TranscriptionSegment(
                start_time=0,
                end_time=self._estimate_text_duration(full_text),
                text=full_text,
                confidence=0.9
            )]

        return full_text, segments

    def _calculate_confidence_score(self, response) -> float:
        """
        Calculate confidence score based on response quality
        This is a simplified implementation

        Args:
            response: Gemini API response

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Basic confidence calculation
        # In production, you might analyze response metadata
        if hasattr(response, 'candidates') and response.candidates:
            # Gemini provides safety ratings and other metadata
            return 0.85  # Default good confidence
        return 0.7  # Lower confidence if limited metadata

    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds"""
        try:
            video = VideoFileClip(video_path)
            duration = video.duration
            video.close()
            return duration
        except:
            return 0.0

    def _estimate_text_duration(self, text: str) -> float:
        """Estimate duration based on text length (rough approximation)"""
        # Assume average speaking rate of ~150 words per minute
        word_count = len(text.split())
        estimated_duration = (word_count / 150) * 60
        return max(estimated_duration, 5.0)  # Minimum 5 seconds