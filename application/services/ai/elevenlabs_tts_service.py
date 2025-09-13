import os
import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.config.settings import settings
from domain.entities.translation import TranslationSegment

logger = logging.getLogger(__name__)


class ElevenLabsTTSService:
    """ElevenLabs Text-to-Speech service with timing preservation"""

    def __init__(self):
        """Initialize ElevenLabs TTS service"""
        if not settings.elevenlabs_api_key or settings.elevenlabs_api_key == "your-elevenlabs-api-key":
            raise ValueError("ElevenLabs API key not configured. Please set ELEVENLABS_API_KEY in your .env file")

        self.api_key = settings.elevenlabs_api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self.default_voice_id = settings.elevenlabs_voice_id
        # Try to initialize official ElevenLabs SDK client
        self.client = None
        try:
            from elevenlabs.client import ElevenLabs  # type: ignore
            self.client = ElevenLabs(api_key=self.api_key)
            logger.info("Initialized ElevenLabs SDK client")
        except Exception as e:
            logger.warning(f"ElevenLabs SDK not available, will use HTTP fallback: {e}")

    async def get_available_voices(self, language_code: str = None) -> List[Dict[str, Any]]:
        """Get available voices, optionally filtered by language"""
        try:
            headers = {
                "Accept": "application/json",
                "xi-api-key": self.api_key
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/voices", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        voices = data.get("voices", [])

                        if language_code:
                            # Filter voices by language if specified
                            filtered_voices = []
                            for voice in voices:
                                voice_languages = [label.get("language") for label in voice.get("labels", {})]
                                if language_code.lower() in [lang.lower() for lang in voice_languages if lang]:
                                    filtered_voices.append(voice)
                            return filtered_voices

                        return voices
                    else:
                        logger.error(f"Failed to get voices: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Error getting voices: {str(e)}")
            return []

    async def select_best_voice(self, target_language: str, country_code: str) -> str:
        """Select the best voice for target language and country"""
        try:
            voices = await self.get_available_voices()

            # Language priority mapping
            language_priorities = {
                "en": ["en-US", "en-GB", "en-AU"],
                "es": ["es-ES", "es-MX", "es-AR"],
                "fr": ["fr-FR", "fr-CA"],
                "de": ["de-DE", "de-AT"],
                "it": ["it-IT"],
                "pt": ["pt-BR", "pt-PT"],
                "ja": ["ja-JP"],
                "ko": ["ko-KR"],
                "zh": ["zh-CN", "zh-TW"],
                "tr": ["tr-TR"],
                "ru": ["ru-RU"],
                "ar": ["ar-SA"]
            }

            # Get language priorities
            lang_priorities = language_priorities.get(target_language.lower(), [target_language])

            # Country-specific voice preferences
            country_voice_map = {
                "US": "en-US", "GB": "en-GB", "AU": "en-AU",
                "ES": "es-ES", "MX": "es-MX", "AR": "es-AR",
                "FR": "fr-FR", "CA": "fr-CA",
                "DE": "de-DE", "AT": "de-AT",
                "BR": "pt-BR", "PT": "pt-PT",
                "TR": "tr-TR"
            }

            preferred_lang = country_voice_map.get(country_code, target_language)

            # Find best voice
            for voice in voices:
                if not isinstance(voice, dict):
                    continue

                voice_labels = voice.get("labels", {})
                if isinstance(voice_labels, list):
                    voice_langs = [label.get("language", "").lower() if isinstance(label, dict) else "" for label in voice_labels]
                elif isinstance(voice_labels, dict):
                    voice_langs = [lang.lower() for lang in voice_labels.values() if isinstance(lang, str)]
                else:
                    voice_langs = []

                if preferred_lang.lower() in voice_langs:
                    return voice.get("voice_id")

            # Fallback to any voice in target language
            for voice in voices:
                if not isinstance(voice, dict):
                    continue

                voice_labels = voice.get("labels", {})
                if isinstance(voice_labels, list):
                    voice_langs = [label.get("language", "").lower() if isinstance(label, dict) else "" for label in voice_labels]
                elif isinstance(voice_labels, dict):
                    voice_langs = [lang.lower() for lang in voice_labels.values() if isinstance(lang, str)]
                else:
                    voice_langs = []

                if target_language.lower() in voice_langs:
                    return voice.get("voice_id")

            # Last fallback - return first available voice
            if voices and len(voices) > 0:
                first_voice = voices[0]
                if isinstance(first_voice, dict) and first_voice.get("voice_id"):
                    return first_voice.get("voice_id")

            return self.default_voice_id

        except Exception as e:
            logger.error(f"Voice selection failed: {str(e)}")
            return self.default_voice_id

    async def generate_speech_for_segments(
        self,
        segments: List[TranslationSegment],
        target_language: str,
        country_code: str,
        output_dir: str
    ) -> List[Dict[str, Any]]:
        """
        Generate speech for translation segments with timing preservation

        Args:
            segments: List of translation segments with timing
            target_language: Target language code
            country_code: Target country code
            output_dir: Directory to save audio files

        Returns:
            List of audio segment info with file paths and timing
        """
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Select best voice
            voice_id = await self.select_best_voice(target_language, country_code)
            logger.info(f"Selected voice {voice_id} for {target_language}-{country_code}")

            audio_segments = []

            for i, segment in enumerate(segments):
                if not segment.translated_text or not segment.translated_text.strip():
                    continue

                try:
                    # Calculate target duration for speed adjustment
                    segment_duration = segment.end_time - segment.start_time

                    # Generate speech for this segment
                    audio_file_path = await self._generate_segment_speech(
                        text=segment.translated_text,
                        voice_id=voice_id,
                        output_path=output_path / f"segment_{i:03d}.mp3",
                        target_duration=segment_duration
                    )

                    if audio_file_path:
                        audio_segments.append({
                            "segment_index": i,
                            "start_time": segment.start_time,
                            "end_time": segment.end_time,
                            "duration": segment_duration,
                            "audio_file": str(audio_file_path),
                            "text": segment.translated_text,
                            "original_text": segment.original_text
                        })

                    # Rate limiting for API
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Failed to generate speech for segment {i}: {str(e)}")
                    continue

            logger.info(f"Generated speech for {len(audio_segments)} segments")
            return audio_segments

        except Exception as e:
            logger.error(f"Speech generation failed: {str(e)}")
            return []

    async def _generate_segment_speech(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        target_duration: float
    ) -> Optional[Path]:
        """Generate speech for a single segment with speed optimization.

        Prefers official ElevenLabs SDK; falls back to HTTP if unavailable.
        """
        # Try SDK first
        if self.client is not None:
            try:
                # Streamed audio generator from SDK
                audio_stream = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )

                # Write stream to file
                with open(output_path, "wb") as f:
                    for chunk in audio_stream:
                        if not chunk:
                            continue
                        if isinstance(chunk, bytes):
                            f.write(chunk)
                        else:
                            try:
                                f.write(bytes(chunk))
                            except Exception:
                                continue

                logger.debug(f"Generated speech via SDK: {output_path}")
                return output_path
            except Exception as e:
                logger.warning(f"ElevenLabs SDK convert failed, falling back to HTTP: {e}")

        # HTTP fallback with speed tuning
        try:
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }

            # Calculate speech speed based on target duration
            # Estimate words per minute based on text length and target duration
            word_count = len(text.split())
            if target_duration > 0 and word_count > 0:
                target_wpm = (word_count / target_duration) * 60
                # Normal speech is around 150-200 WPM
                if target_wpm > 250:
                    # Speech too fast, use faster settings
                    speed = 1.2
                    stability = 0.3
                elif target_wpm < 100:
                    # Speech too slow, use slower settings
                    speed = 0.8
                    stability = 0.8
                else:
                    # Normal speech
                    speed = 1.0
                    stability = 0.5
            else:
                speed = 1.0
                stability = 0.5

            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": 0.75,
                    "style": 0.5,
                    "use_speaker_boost": True,
                    "speed": speed
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/text-to-speech/{voice_id}",
                    json=data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        # Save audio data
                        audio_data = await response.read()
                        with open(output_path, 'wb') as f:
                            f.write(audio_data)

                        logger.debug(f"Generated speech: {output_path}")
                        return output_path
                    else:
                        error_text = await response.text()
                        logger.error(f"TTS API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Speech generation failed for segment: {str(e)}")
            return None

    async def generate_full_audio_track(
        self,
        audio_segments: List[Dict[str, Any]],
        total_duration: float,
        output_path: str
    ) -> Optional[str]:
        """
        Combine audio segments into a full audio track with proper timing

        Args:
            audio_segments: List of audio segments with timing info
            total_duration: Total duration of the original video
            output_path: Path for the combined audio file

        Returns:
            Path to combined audio file or None if failed
        """
        try:
            # This requires FFmpeg to be installed
            import subprocess
            from tempfile import NamedTemporaryFile

            # Create FFmpeg filter complex for precise timing
            filter_parts = []
            input_files = []

            for i, segment in enumerate(audio_segments):
                if not os.path.exists(segment["audio_file"]):
                    continue

                input_files.extend(["-i", segment["audio_file"]])

                # Add silence before this segment if needed
                start_time = segment["start_time"]

                # Create filter for this segment with precise timing
                filter_parts.append(f"[{i}:0]adelay={int(start_time * 1000)}|{int(start_time * 1000)}[delayed{i}]")

            if not filter_parts:
                logger.error("No valid audio segments to combine")
                return None

            # Combine all delayed segments
            mix_inputs = "".join([f"[delayed{i}]" for i in range(len(filter_parts))])
            mix_filter = f"{mix_inputs}amix=inputs={len(filter_parts)}:duration=longest"

            # Build full filter complex
            filter_complex = ";".join(filter_parts + [mix_filter])

            # FFmpeg command
            cmd = [
                "ffmpeg", "-y",  # Overwrite output
                *input_files,  # Input files
                "-filter_complex", filter_complex,
                "-t", str(total_duration),  # Limit to video duration
                "-c:a", "aac",  # Audio codec
                "-b:a", "128k",  # Audio bitrate
                output_path
            ]

            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Combined audio track created: {output_path}")
                return output_path
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Audio combination failed: {str(e)}")
            return None
