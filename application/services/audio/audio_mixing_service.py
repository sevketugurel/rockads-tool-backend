import os
import asyncio
import logging
import subprocess
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
import tempfile
import json
from dataclasses import dataclass

from core.config.settings import settings
from domain.entities.translation import TranslationSegment

logger = logging.getLogger(__name__)


@dataclass
class AudioMixConfig:
    """Configuration for audio mixing operations"""
    voice_volume: float = 1.0  # Main voice volume (0.0-2.0)
    background_volume: float = 0.3  # Background music volume (0.0-1.0)
    crossfade_duration: float = 0.2  # Crossfade between segments in seconds
    normalize_audio: bool = True  # Apply audio normalization
    compression_ratio: float = 2.0  # Audio compression ratio (1.0 = no compression)
    noise_reduction: bool = True  # Apply noise reduction to voice
    stereo_enhancement: bool = False  # Enhance stereo separation
    output_format: str = "wav"  # Output audio format
    sample_rate: int = 44100  # Output sample rate
    bitrate: str = "192k"  # Output bitrate for compressed formats


class AudioMixingService:
    """
    Advanced audio mixing service for combining localized voice with preserved background music.
    Provides professional-quality audio mixing with timing synchronization and quality optimization.
    """

    def __init__(self, temp_dir: str = None, output_dir: str = None):
        """Initialize audio mixing service"""
        self.temp_dir = Path(temp_dir) if temp_dir else Path(settings.temp_dir)
        self.output_dir = Path(output_dir) if output_dir else Path(settings.output_dir)

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def mix_voice_with_background(
        self,
        voice_audio_path: str,
        background_audio_path: str,
        output_path: str,
        config: AudioMixConfig = None
    ) -> Optional[str]:
        """
        Mix localized voice audio with preserved background music/ambient sounds

        Args:
            voice_audio_path: Path to localized voice audio
            background_audio_path: Path to preserved background/music audio
            output_path: Path for mixed output audio
            config: Mixing configuration settings

        Returns:
            Path to mixed audio file or None if failed
        """
        try:
            if config is None:
                config = AudioMixConfig()

            logger.info(f"Mixing voice with background: voice={voice_audio_path}, background={background_audio_path}")

            # Validate input files
            if not os.path.exists(voice_audio_path):
                raise FileNotFoundError(f"Voice audio file not found: {voice_audio_path}")
            if not os.path.exists(background_audio_path):
                raise FileNotFoundError(f"Background audio file not found: {background_audio_path}")

            # Get audio properties
            voice_info = await self._get_audio_info(voice_audio_path)
            bg_info = await self._get_audio_info(background_audio_path)

            if not voice_info or not bg_info:
                raise Exception("Failed to analyze input audio files")

            # Create mixing command
            result_path = await self._mix_audio_tracks(
                voice_audio_path, background_audio_path, output_path, config, voice_info, bg_info
            )

            if result_path and os.path.exists(result_path):
                logger.info(f"Audio mixing completed: {result_path}")
                return result_path
            else:
                raise Exception("Audio mixing failed - output file not created")

        except Exception as e:
            logger.error(f"Audio mixing failed: {str(e)}")
            return None

    async def mix_segmented_voice_with_background(
        self,
        voice_segments: List[Dict[str, Any]],
        background_audio_path: str,
        output_path: str,
        total_duration: float,
        config: AudioMixConfig = None
    ) -> Optional[str]:
        """
        Mix segmented voice audio with continuous background music

        Args:
            voice_segments: List of voice segments with timing and file paths
            background_audio_path: Path to preserved background audio
            output_path: Path for mixed output audio
            total_duration: Total duration of the final audio
            config: Mixing configuration settings

        Returns:
            Path to mixed audio file or None if failed
        """
        try:
            if config is None:
                config = AudioMixConfig()

            logger.info(f"Mixing {len(voice_segments)} voice segments with background")

            # Create temporary combined voice track
            temp_voice_path = self.temp_dir / f"temp_voice_{int(asyncio.get_event_loop().time())}.{config.output_format}"

            combined_voice = await self._combine_voice_segments(
                voice_segments, str(temp_voice_path), total_duration, config
            )

            if not combined_voice:
                raise Exception("Failed to combine voice segments")

            # Mix combined voice with background
            result_path = await self.mix_voice_with_background(
                str(temp_voice_path), background_audio_path, output_path, config
            )

            # Clean up temporary file
            if temp_voice_path.exists():
                temp_voice_path.unlink()

            return result_path

        except Exception as e:
            logger.error(f"Segmented audio mixing failed: {str(e)}")
            return None

    async def _mix_audio_tracks(
        self,
        voice_path: str,
        background_path: str,
        output_path: str,
        config: AudioMixConfig,
        voice_info: Dict[str, Any],
        bg_info: Dict[str, Any]
    ) -> Optional[str]:
        """Mix two audio tracks with advanced processing"""
        try:
            # Build FFmpeg filter complex for professional mixing
            filter_parts = []

            # Voice processing chain
            voice_filters = []

            # Volume adjustment
            voice_filters.append(f"volume={config.voice_volume}")

            # Noise reduction if enabled
            if config.noise_reduction:
                voice_filters.append("afftdn=nf=-25")  # Noise reduction

            # Compression for better dynamics
            if config.compression_ratio > 1.0:
                voice_filters.append(f"compand=attacks=0.1:decays=0.8:points=-80/-80|-10/-10|0/-{3*config.compression_ratio}")

            # EQ for voice clarity
            voice_filters.append("firequalizer=gain_entry='entry(100,0);entry(200,2);entry(1000,3);entry(3000,4);entry(6000,2);entry(12000,0)'")

            voice_filter_chain = ",".join(voice_filters)
            filter_parts.append(f"[0:a]{voice_filter_chain}[voice]")

            # Background processing chain
            bg_filters = []

            # Volume adjustment
            bg_filters.append(f"volume={config.background_volume}")

            # EQ for background (reduce mid frequencies to make room for voice)
            bg_filters.append("firequalizer=gain_entry='entry(100,0);entry(500,-2);entry(2000,-3);entry(4000,-2);entry(8000,0)'")

            # Stereo enhancement if enabled
            if config.stereo_enhancement:
                bg_filters.append("extrastereo=m=2.5")

            bg_filter_chain = ",".join(bg_filters)
            filter_parts.append(f"[1:a]{bg_filter_chain}[background]")

            # Mix the processed tracks
            mix_filter = f"[voice][background]amix=inputs=2:duration=longest:dropout_transition={config.crossfade_duration}"
            filter_parts.append(mix_filter)

            # Final processing
            final_filters = []

            # Normalization if enabled
            if config.normalize_audio:
                final_filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")  # Broadcast standard normalization

            # Final limiting to prevent clipping
            final_filters.append("alimiter=limit=0.95")

            if final_filters:
                final_filter_chain = ",".join(final_filters)
                filter_parts[-1] += f",{final_filter_chain}"

            # Complete filter complex
            filter_complex = ";".join(filter_parts)

            # Build FFmpeg command
            cmd = [
                "ffmpeg", "-y",
                "-i", voice_path,
                "-i", background_path,
                "-filter_complex", filter_complex,
                "-ar", str(config.sample_rate),
                "-ac", "2",  # Stereo output
            ]

            # Add codec and bitrate settings
            if config.output_format.lower() == "mp3":
                cmd.extend(["-c:a", "libmp3lame", "-b:a", config.bitrate])
            elif config.output_format.lower() == "aac":
                cmd.extend(["-c:a", "aac", "-b:a", config.bitrate])
            else:  # WAV or other
                cmd.extend(["-c:a", "pcm_s16le"])

            cmd.append(output_path)

            logger.debug(f"FFmpeg mixing command: {' '.join(cmd)}")

            # Execute mixing command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"FFmpeg mixing failed: {error_msg}")

            return output_path

        except Exception as e:
            logger.error(f"Audio track mixing failed: {str(e)}")
            return None

    async def _combine_voice_segments(
        self,
        voice_segments: List[Dict[str, Any]],
        output_path: str,
        total_duration: float,
        config: AudioMixConfig
    ) -> Optional[str]:
        """Combine multiple voice segments into a single track with precise timing"""
        try:
            if not voice_segments:
                logger.warning("No voice segments provided")
                return None

            # Build FFmpeg command for segment combination
            cmd = ["ffmpeg", "-y"]
            filter_parts = []

            # Add input files
            input_count = 0
            valid_segments = []

            for segment in voice_segments:
                audio_file = segment.get("audio_file")
                if audio_file and os.path.exists(audio_file):
                    cmd.extend(["-i", audio_file])
                    valid_segments.append({
                        **segment,
                        "input_index": input_count
                    })
                    input_count += 1

            if not valid_segments:
                logger.error("No valid voice segments found")
                return None

            # Create silence as base track
            silence_filter = f"anullsrc=channel_layout=stereo:sample_rate={config.sample_rate}:duration={total_duration}[silence]"
            filter_parts.append(silence_filter)

            # Process each segment with timing and crossfades
            segment_filters = []
            for i, segment in enumerate(valid_segments):
                input_idx = segment["input_index"]
                start_time = segment.get("start_time", 0)
                end_time = segment.get("end_time", start_time + 1)
                duration = end_time - start_time

                # Calculate delays and fades
                delay_ms = int(start_time * 1000)
                fade_duration = min(config.crossfade_duration, duration / 4)

                # Create filter for this segment
                segment_filter = (
                    f"[{input_idx}:a]"
                    f"adelay={delay_ms}|{delay_ms},"
                    f"afade=t=in:ss=0:d={fade_duration},"
                    f"afade=t=out:st={duration-fade_duration}:d={fade_duration},"
                    f"volume={config.voice_volume}[seg{i}]"
                )
                filter_parts.append(segment_filter)
                segment_filters.append(f"[seg{i}]")

            # Mix silence with all segments
            mix_inputs = "[silence]" + "".join(segment_filters)
            mix_filter = f"{mix_inputs}amix=inputs={len(segment_filters)+1}:duration=first:dropout_transition={config.crossfade_duration}"
            filter_parts.append(mix_filter)

            # Complete filter complex
            filter_complex = ";".join(filter_parts)

            # Add filter and output settings
            cmd.extend([
                "-filter_complex", filter_complex,
                "-t", str(total_duration),
                "-ar", str(config.sample_rate),
                "-ac", "2",
                "-c:a", "pcm_s16le",
                output_path
            ])

            logger.debug(f"Voice segment combination command: {' '.join(cmd)}")

            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"Voice segment combination failed: {error_msg}")

            return output_path

        except Exception as e:
            logger.error(f"Voice segment combination failed: {str(e)}")
            return None

    async def _get_audio_info(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an audio file"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_entries", "stream=channels,sample_rate,bit_rate,duration,codec_name",
                "-show_entries", "format=duration,bit_rate,size",
                audio_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"FFprobe failed for {audio_path}: {stderr.decode()}")
                return None

            probe_data = json.loads(stdout.decode())

            # Find audio stream
            audio_stream = None
            for stream in probe_data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    audio_stream = stream
                    break

            if not audio_stream:
                return None

            format_info = probe_data.get("format", {})

            return {
                "duration": float(format_info.get("duration", 0)),
                "channels": int(audio_stream.get("channels", 0)),
                "sample_rate": int(audio_stream.get("sample_rate", 0)),
                "bit_rate": int(audio_stream.get("bit_rate", 0)),
                "codec": audio_stream.get("codec_name", "unknown"),
                "size": int(format_info.get("size", 0))
            }

        except Exception as e:
            logger.error(f"Audio info analysis failed for {audio_path}: {str(e)}")
            return None

    async def analyze_mix_quality(
        self,
        mixed_audio_path: str,
        original_voice_path: str = None,
        original_background_path: str = None
    ) -> Dict[str, Any]:
        """
        Analyze the quality of the mixed audio

        Args:
            mixed_audio_path: Path to mixed audio file
            original_voice_path: Optional path to original voice for comparison
            original_background_path: Optional path to original background for comparison

        Returns:
            Quality analysis results
        """
        try:
            if not os.path.exists(mixed_audio_path):
                return {"error": "Mixed audio file not found"}

            # Get basic audio properties
            audio_info = await self._get_audio_info(mixed_audio_path)
            if not audio_info:
                return {"error": "Could not analyze mixed audio"}

            # Analyze audio levels and dynamics
            levels = await self._analyze_audio_levels(mixed_audio_path)

            quality_score = self._calculate_mix_quality_score(audio_info, levels)

            return {
                "audio_info": audio_info,
                "audio_levels": levels,
                "quality_score": quality_score,
                "recommendations": self._generate_quality_recommendations(audio_info, levels)
            }

        except Exception as e:
            logger.error(f"Mix quality analysis failed: {str(e)}")
            return {"error": str(e)}

    async def _analyze_audio_levels(self, audio_path: str) -> Dict[str, float]:
        """Analyze audio levels and dynamics using FFmpeg"""
        try:
            # Analyze loudness and dynamics
            cmd = [
                "ffmpeg", "-i", audio_path,
                "-filter:a", "astats=metadata=1:reset=1",
                "-f", "null", "-"
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            # Parse stderr for audio statistics
            stderr_text = stderr.decode()

            levels = {}

            # Extract key measurements from FFmpeg output
            for line in stderr_text.split('\n'):
                if 'RMS level dB:' in line:
                    try:
                        rms = float(line.split('RMS level dB:')[1].strip())
                        levels['rms_db'] = rms
                    except:
                        pass
                elif 'Max level dB:' in line:
                    try:
                        max_level = float(line.split('Max level dB:')[1].strip())
                        levels['max_db'] = max_level
                    except:
                        pass
                elif 'Dynamic range:' in line:
                    try:
                        dynamic_range = float(line.split('Dynamic range:')[1].strip())
                        levels['dynamic_range'] = dynamic_range
                    except:
                        pass

            return levels

        except Exception as e:
            logger.error(f"Audio level analysis failed: {str(e)}")
            return {}

    def _calculate_mix_quality_score(
        self,
        audio_info: Dict[str, Any],
        levels: Dict[str, float]
    ) -> float:
        """Calculate overall quality score for the mix"""
        try:
            score = 0.0
            factors = 0

            # Sample rate score (higher is better)
            if audio_info.get("sample_rate", 0) >= 44100:
                score += 0.3
            elif audio_info.get("sample_rate", 0) >= 22050:
                score += 0.2
            factors += 0.3

            # Channels score (stereo preferred)
            if audio_info.get("channels", 0) >= 2:
                score += 0.2
            factors += 0.2

            # RMS level score (should be reasonable, not too quiet or loud)
            rms_db = levels.get("rms_db", -60)
            if -20 <= rms_db <= -6:  # Good range
                score += 0.3
            elif -30 <= rms_db <= -3:  # Acceptable
                score += 0.2
            factors += 0.3

            # Dynamic range score
            dynamic_range = levels.get("dynamic_range", 0)
            if dynamic_range >= 10:  # Good dynamics
                score += 0.2
            elif dynamic_range >= 6:  # Acceptable
                score += 0.1
            factors += 0.2

            # Normalize score
            if factors > 0:
                return min(score / factors, 1.0)
            else:
                return 0.5  # Default medium score

        except Exception:
            return 0.5

    def _generate_quality_recommendations(
        self,
        audio_info: Dict[str, Any],
        levels: Dict[str, float]
    ) -> List[str]:
        """Generate recommendations for improving mix quality"""
        recommendations = []

        try:
            # Sample rate recommendations
            sample_rate = audio_info.get("sample_rate", 0)
            if sample_rate < 44100:
                recommendations.append(f"Consider using higher sample rate (current: {sample_rate}Hz, recommended: 44100Hz+)")

            # Level recommendations
            rms_db = levels.get("rms_db", -60)
            if rms_db < -30:
                recommendations.append("Audio levels are too low - consider increasing voice volume")
            elif rms_db > -6:
                recommendations.append("Audio levels are too high - risk of clipping, consider reducing volume")

            # Dynamic range recommendations
            dynamic_range = levels.get("dynamic_range", 0)
            if dynamic_range < 6:
                recommendations.append("Low dynamic range - consider reducing compression")

            # Maximum level check
            max_db = levels.get("max_db", -60)
            if max_db > -0.5:
                recommendations.append("Peak levels too high - apply limiting to prevent clipping")

            if not recommendations:
                recommendations.append("Audio mix quality looks good!")

        except Exception:
            recommendations.append("Could not generate quality recommendations")

        return recommendations

    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up temporary mixing files older than specified hours"""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            for item in self.temp_dir.iterdir():
                if item.is_file() and item.name.startswith("temp_"):
                    # Check if file is old enough
                    file_age = current_time - item.stat().st_mtime
                    if file_age > max_age_seconds:
                        item.unlink()
                        logger.info(f"Cleaned up old temp file: {item}")

        except Exception as e:
            logger.error(f"Temp file cleanup failed: {str(e)}")