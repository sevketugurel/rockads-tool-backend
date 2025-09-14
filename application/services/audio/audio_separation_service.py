import os
import asyncio
import logging
import subprocess
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import tempfile
import json

from core.config.settings import settings

logger = logging.getLogger(__name__)


class AudioSeparationService:
    """
    Advanced audio separation service for isolating vocals from background music/ambient sounds.
    Uses Spleeter for high-quality, real-time audio source separation.
    """

    def __init__(self, temp_dir: str = None):
        """Initialize audio separation service with Spleeter integration"""
        self.temp_dir = Path(temp_dir) if temp_dir else Path(settings.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Spleeter model configurations
        self.spleeter_models = {
            "2stems": "2stems-16kHz",  # Vocals + accompaniment
            "4stems": "4stems-16kHz",  # Vocals + drums + bass + other
            "5stems": "5stems-16kHz"   # Vocals + drums + bass + piano + other
        }

        # Check Spleeter availability
        self._check_spleeter_availability()

    def _check_spleeter_availability(self):
        """Check if Spleeter is available in the system"""
        try:
            result = subprocess.run(
                ["spleeter", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info("Spleeter is available and ready")
                self.spleeter_available = True
            else:
                logger.warning("Spleeter command failed, will use fallback methods")
                self.spleeter_available = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Spleeter not found in PATH, will use fallback methods")
            self.spleeter_available = False

    async def separate_audio_sources(
        self,
        audio_file_path: str,
        model_type: str = "2stems",
        output_format: str = "wav"
    ) -> Dict[str, str]:
        """
        Separate audio into different sources (vocals, accompaniment, etc.)

        Args:
            audio_file_path: Path to input audio file
            model_type: Spleeter model to use ("2stems", "4stems", "5stems")
            output_format: Output audio format ("wav", "mp3")

        Returns:
            Dictionary mapping source names to output file paths
        """
        try:
            if not os.path.exists(audio_file_path):
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

            logger.info(f"Separating audio sources from {audio_file_path} using {model_type} model")

            # Create unique output directory
            output_dir = self.temp_dir / f"separation_{int(asyncio.get_event_loop().time())}"
            output_dir.mkdir(exist_ok=True)

            if self.spleeter_available:
                return await self._separate_with_spleeter(
                    audio_file_path, model_type, output_dir, output_format
                )
            else:
                return await self._separate_with_ffmpeg_fallback(
                    audio_file_path, output_dir, output_format
                )

        except Exception as e:
            logger.error(f"Audio separation failed: {str(e)}")
            raise

    async def _separate_with_spleeter(
        self,
        audio_file_path: str,
        model_type: str,
        output_dir: Path,
        output_format: str
    ) -> Dict[str, str]:
        """Separate audio using Spleeter"""
        try:
            model_name = self.spleeter_models.get(model_type, "2stems-16kHz")

            # Run Spleeter separation
            cmd = [
                "spleeter", "separate",
                "-p", model_name,
                "-o", str(output_dir),
                "-f", f"{{{output_format}}}",
                audio_file_path
            ]

            logger.debug(f"Running Spleeter: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"Spleeter separation failed: {error_msg}")

            # Find and organize output files
            audio_filename = Path(audio_file_path).stem
            separation_dir = output_dir / audio_filename

            result_files = {}

            if separation_dir.exists():
                for file_path in separation_dir.glob(f"*.{output_format}"):
                    source_name = file_path.stem
                    result_files[source_name] = str(file_path)

            logger.info(f"Spleeter separation completed: {list(result_files.keys())}")
            return result_files

        except Exception as e:
            logger.error(f"Spleeter separation failed: {str(e)}")
            raise

    async def _separate_with_ffmpeg_fallback(
        self,
        audio_file_path: str,
        output_dir: Path,
        output_format: str
    ) -> Dict[str, str]:
        """Fallback audio separation using FFmpeg vocal isolation techniques"""
        try:
            logger.info("Using FFmpeg fallback for audio separation")

            audio_filename = Path(audio_file_path).stem

            # Extract vocals using center channel subtraction
            vocals_path = output_dir / f"{audio_filename}_vocals.{output_format}"
            accompaniment_path = output_dir / f"{audio_filename}_accompaniment.{output_format}"

            # Vocal isolation: pan=stereo|c0=c0-c1|c1=c1-c0 (subtracts center channel)
            vocal_cmd = [
                "ffmpeg", "-y",
                "-i", audio_file_path,
                "-filter_complex",
                "[0:a]pan=stereo|c0=c0-c1|c1=c1-c0,volume=2.0[vocals]",
                "-map", "[vocals]",
                "-c:a", "pcm_s16le" if output_format == "wav" else "mp3",
                str(vocals_path)
            ]

            # Background/accompaniment: Keep original with reduced vocals
            accompaniment_cmd = [
                "ffmpeg", "-y",
                "-i", audio_file_path,
                "-filter_complex",
                "[0:a]compand=attacks=0.1:decays=0.8:points=-80/-80|-10/-10|0/-3,volume=0.8[bg]",
                "-map", "[bg]",
                "-c:a", "pcm_s16le" if output_format == "wav" else "mp3",
                str(accompaniment_path)
            ]

            # Run vocal extraction
            process = await asyncio.create_subprocess_exec(
                *vocal_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            # Run background extraction
            process = await asyncio.create_subprocess_exec(
                *accompaniment_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            result_files = {}
            if vocals_path.exists():
                result_files["vocals"] = str(vocals_path)
            if accompaniment_path.exists():
                result_files["accompaniment"] = str(accompaniment_path)

            logger.info(f"FFmpeg separation completed: {list(result_files.keys())}")
            return result_files

        except Exception as e:
            logger.error(f"FFmpeg separation failed: {str(e)}")
            raise

    async def extract_vocals_only(self, audio_file_path: str) -> Optional[str]:
        """
        Extract only the vocal track from audio file

        Args:
            audio_file_path: Path to input audio file

        Returns:
            Path to extracted vocals file or None if failed
        """
        try:
            separated = await self.separate_audio_sources(audio_file_path, "2stems")
            return separated.get("vocals")
        except Exception as e:
            logger.error(f"Vocal extraction failed: {str(e)}")
            return None

    async def extract_background_only(self, audio_file_path: str) -> Optional[str]:
        """
        Extract only the background/accompaniment track from audio file

        Args:
            audio_file_path: Path to input audio file

        Returns:
            Path to extracted background file or None if failed
        """
        try:
            separated = await self.separate_audio_sources(audio_file_path, "2stems")
            return separated.get("accompaniment")
        except Exception as e:
            logger.error(f"Background extraction failed: {str(e)}")
            return None

    async def analyze_separation_quality(
        self,
        original_audio_path: str,
        separated_files: Dict[str, str]
    ) -> Dict[str, float]:
        """
        Analyze the quality of audio separation using signal analysis

        Args:
            original_audio_path: Path to original audio file
            separated_files: Dictionary of separated audio files

        Returns:
            Quality metrics for each separated track
        """
        try:
            quality_metrics = {}

            for source_name, file_path in separated_files.items():
                if not os.path.exists(file_path):
                    continue

                # Use FFmpeg to analyze audio properties
                cmd = [
                    "ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_entries", "stream=bit_rate,sample_rate,channels,duration",
                    "-show_entries", "format=bit_rate,duration,size",
                    file_path
                ]

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    probe_data = json.loads(stdout.decode())

                    # Extract audio stream info
                    audio_stream = None
                    for stream in probe_data.get("streams", []):
                        if stream.get("codec_type") == "audio":
                            audio_stream = stream
                            break

                    if audio_stream:
                        quality_score = self._calculate_quality_score(audio_stream)
                        quality_metrics[source_name] = quality_score

            return quality_metrics

        except Exception as e:
            logger.error(f"Quality analysis failed: {str(e)}")
            return {}

    def _calculate_quality_score(self, audio_stream: Dict[str, Any]) -> float:
        """Calculate quality score based on audio stream properties"""
        try:
            # Basic quality scoring based on bitrate and sample rate
            bitrate = int(audio_stream.get("bit_rate", 0))
            sample_rate = int(audio_stream.get("sample_rate", 0))
            channels = int(audio_stream.get("channels", 0))

            # Normalize scores (0-1 scale)
            bitrate_score = min(bitrate / 320000, 1.0)  # 320kbps as maximum
            sample_rate_score = min(sample_rate / 48000, 1.0)  # 48kHz as maximum
            channel_score = min(channels / 2.0, 1.0)  # Stereo as maximum

            # Weighted average
            quality_score = (
                bitrate_score * 0.5 +
                sample_rate_score * 0.3 +
                channel_score * 0.2
            )

            return round(quality_score, 3)

        except Exception:
            return 0.5  # Default medium quality score

    async def get_separation_info(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Get information about potential separation quality for an audio file

        Args:
            audio_file_path: Path to audio file

        Returns:
            Information about separation feasibility and expected quality
        """
        try:
            # Analyze audio properties
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_entries", "stream=channels,sample_rate,bit_rate,codec_name",
                "-show_entries", "format=duration,bit_rate",
                audio_file_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return {"error": "Could not analyze audio file"}

            probe_data = json.loads(stdout.decode())

            # Find audio stream
            audio_stream = None
            for stream in probe_data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    audio_stream = stream
                    break

            if not audio_stream:
                return {"error": "No audio stream found"}

            channels = int(audio_stream.get("channels", 0))
            sample_rate = int(audio_stream.get("sample_rate", 0))
            duration = float(probe_data.get("format", {}).get("duration", 0))

            # Assess separation feasibility
            separation_feasible = channels >= 2  # Need stereo for vocal isolation
            expected_quality = "high" if sample_rate >= 44100 else "medium" if sample_rate >= 22050 else "low"

            processing_time_estimate = duration * 0.1  # Roughly 10% of audio duration

            return {
                "separation_feasible": separation_feasible,
                "expected_quality": expected_quality,
                "channels": channels,
                "sample_rate": sample_rate,
                "duration": duration,
                "estimated_processing_time": processing_time_estimate,
                "recommended_model": "2stems" if separation_feasible else None,
                "spleeter_available": self.spleeter_available
            }

        except Exception as e:
            logger.error(f"Separation info analysis failed: {str(e)}")
            return {"error": str(e)}

    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up temporary separation files older than specified hours"""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            for item in self.temp_dir.iterdir():
                if item.is_dir() and item.name.startswith("separation_"):
                    # Check if directory is old enough
                    dir_age = current_time - item.stat().st_mtime
                    if dir_age > max_age_seconds:
                        # Remove directory and all contents
                        import shutil
                        shutil.rmtree(item)
                        logger.info(f"Cleaned up old separation directory: {item}")

        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")