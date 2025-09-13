import os
import subprocess
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
import json

logger = logging.getLogger(__name__)


class VideoProcessingService:
    """Advanced video processing service with audio synchronization and scene awareness"""

    def __init__(self, temp_dir: str = "temp", output_dir: str = "output"):
        """Initialize video processing service"""
        self.temp_dir = Path(temp_dir)
        self.output_dir = Path(output_dir)

        # Create directories if they don't exist
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def replace_audio_with_synchronization(
        self,
        original_video_path: str,
        new_audio_path: str,
        output_video_path: str,
        preserve_original_audio_volume: float = 0.1,
        fade_transitions: bool = True
    ) -> Optional[str]:
        """
        Replace video audio with new localized audio while preserving timing and adding smooth transitions

        Args:
            original_video_path: Path to original video
            new_audio_path: Path to new localized audio
            output_video_path: Path for output video
            preserve_original_audio_volume: Volume level for background original audio (0.0-1.0)
            fade_transitions: Whether to add fade transitions between segments

        Returns:
            Path to processed video or None if failed
        """
        try:
            logger.info(f"Processing video with audio replacement: {original_video_path}")

            # Load original video
            video = VideoFileClip(original_video_path)
            original_audio = video.audio
            duration = video.duration

            # Load new audio
            new_audio = AudioFileClip(new_audio_path)

            # Ensure new audio matches video duration
            if new_audio.duration != duration:
                if new_audio.duration > duration:
                    # Trim audio if longer
                    new_audio = new_audio.subclip(0, duration)
                else:
                    # Extend audio if shorter (with silence)
                    from moviepy.audio.fx import afx
                    silence_duration = duration - new_audio.duration
                    if silence_duration > 0:
                        # Create silence and concatenate
                        silence = AudioFileClip(None, duration=silence_duration)
                        new_audio = CompositeAudioClip([new_audio, silence.set_start(new_audio.duration)])

            # Create composite audio
            if preserve_original_audio_volume > 0 and original_audio:
                # Mix new audio with reduced original audio for background ambience
                background_audio = original_audio.volumex(preserve_original_audio_volume)
                composite_audio = CompositeAudioClip([
                    new_audio.volumex(1.0),  # New audio at full volume
                    background_audio  # Original audio at reduced volume
                ])
            else:
                composite_audio = new_audio

            # Apply fade effects if requested
            if fade_transitions:
                composite_audio = composite_audio.audio_fadein(0.5).audio_fadeout(0.5)

            # Set the new audio to video
            final_video = video.set_audio(composite_audio)

            # Write the result
            final_video.write_videofile(
                output_video_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None
            )

            # Clean up
            video.close()
            new_audio.close()
            if original_audio:
                original_audio.close()
            composite_audio.close()
            final_video.close()

            logger.info(f"Video processing completed: {output_video_path}")
            return output_video_path

        except Exception as e:
            logger.error(f"Video processing failed: {str(e)}")
            return None

    async def create_synchronized_video_with_segments(
        self,
        original_video_path: str,
        audio_segments: List[Dict[str, Any]],
        output_video_path: str,
        background_audio_volume: float = 0.05,
        isolate_music: bool = False
    ) -> Optional[str]:
        """
        Create video with precisely synchronized audio segments

        Args:
            original_video_path: Path to original video
            audio_segments: List of audio segments with timing information
            output_video_path: Path for output video
            background_audio_volume: Volume for original background audio

        Returns:
            Path to processed video or None if failed
        """
        try:
            logger.info(f"Creating synchronized video with {len(audio_segments)} segments")

            video = VideoFileClip(original_video_path)
            duration = video.duration

            # Create temporary combined audio file
            temp_audio_path = self.temp_dir / "temp_combined_audio.wav"

            # Use FFmpeg for precise audio timing
            success = await self._create_precise_audio_track(
                audio_segments=audio_segments,
                total_duration=duration,
                output_path=str(temp_audio_path),
                original_video_path=original_video_path,
                background_volume=background_audio_volume,
                isolate_music=isolate_music
            )

            if not success:
                logger.error("Failed to create precise audio track")
                return None

            # Replace video audio with the new synchronized track
            result = await self.replace_audio_with_synchronization(
                original_video_path=original_video_path,
                new_audio_path=str(temp_audio_path),
                output_video_path=output_video_path,
                preserve_original_audio_volume=0,  # Don't preserve original since we already mixed it
                fade_transitions=False  # We handle transitions in the audio creation
            )

            # Clean up temporary file
            if temp_audio_path.exists():
                temp_audio_path.unlink()

            return result

        except Exception as e:
            logger.error(f"Synchronized video creation failed: {str(e)}")
            return None

    async def _create_precise_audio_track(
        self,
        audio_segments: List[Dict[str, Any]],
        total_duration: float,
        output_path: str,
        original_video_path: str,
        background_volume: float = 0.05,
        isolate_music: bool = False
    ) -> bool:
        """Create precisely timed audio track using FFmpeg"""
        try:
            # Build FFmpeg command for complex audio mixing
            cmd = ["ffmpeg", "-y"]  # -y to overwrite output

            # Add original video as input for background audio
            cmd.extend(["-i", original_video_path])

            # Add all segment audio files as inputs
            input_count = 1  # Start from 1 since 0 is the original video
            segment_inputs = []

            for segment in audio_segments:
                if os.path.exists(segment["audio_file"]):
                    cmd.extend(["-i", segment["audio_file"]])
                    segment_inputs.append({
                        "index": input_count,
                        "start_time": segment["start_time"],
                        "end_time": segment["end_time"],
                        "duration": segment["duration"]
                    })
                    input_count += 1

            if not segment_inputs:
                logger.error("No valid audio segments found")
                return False

            # Build filter complex
            filter_parts = []

            # Extract and reduce original audio as background.
            # If isolate_music is True, attempt to attenuate centered vocals using mid/side subtraction.
            if isolate_music:
                # Simple vocal reduction technique (works when vocals are center-panned)
                # pan=stereo|c0=c0-c1|c1=c1-c0 will cancel the mid (center) channel.
                # Then apply slight low/highpass shaping to keep music body and reduce artifacts.
                filter_parts.append(
                    f"[0:a]pan=stereo|c0=c0-c1|c1=c1-c0,"
                    f"alimiter=limit=0.9,"
                    f"firequalizer=gain_entry='entry(100, -3);entry(1000, -6);entry(5000, -4)',"
                    f"volume={background_volume}[bg]"
                )
            else:
                filter_parts.append(f"[0:a]volume={background_volume}[bg]")

            # Process each segment with precise timing and crossfading
            for i, seg_input in enumerate(segment_inputs):
                input_idx = seg_input["index"]
                start_time = seg_input["start_time"]

                # Add delay and fade effects for smooth transitions
                delay_ms = int(start_time * 1000)

                # Create fade in/out for smoother transitions
                fade_duration = min(0.3, seg_input["duration"] / 4)  # Fade for 0.3s or 1/4 of duration

                filter_parts.append(
                    f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},"
                    f"afade=t=in:ss=0:d={fade_duration},"
                    f"afade=t=out:st={seg_input['duration']-fade_duration}:d={fade_duration}[seg{i}]"
                )

            # Mix background and all segments
            mix_inputs = "[bg]"
            for i in range(len(segment_inputs)):
                mix_inputs += f"[seg{i}]"

            mix_filter = f"{mix_inputs}amix=inputs={len(segment_inputs)+1}:duration=longest:dropout_transition=0.2"
            filter_parts.append(mix_filter)

            # Combine all filter parts
            filter_complex = ";".join(filter_parts)

            # Add filter complex and output settings
            cmd.extend([
                "-filter_complex", filter_complex,
                "-t", str(total_duration),  # Limit to video duration
                "-c:a", "pcm_s16le",  # Use uncompressed audio for better quality
                "-ar", "44100",  # Sample rate
                output_path
            ])

            # Execute FFmpeg command
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Precise audio track created: {output_path}")
                return True
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Precise audio track creation failed: {str(e)}")
            return False

    async def analyze_scene_transitions(self, video_path: str, segment_timings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze video for scene transitions to optimize audio segment placement

        Args:
            video_path: Path to video file
            segment_timings: List of segment timing information

        Returns:
            Enhanced segment information with scene transition data
        """
        try:
            # Use FFmpeg to detect scene changes
            cmd = [
                "ffmpeg", "-i", video_path,
                "-filter:v", "select='gt(scene,0.3)',showinfo",
                "-f", "null", "-"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Parse scene change timestamps from FFmpeg output
            scene_changes = []
            for line in result.stderr.split('\n'):
                if 'pts_time:' in line:
                    try:
                        # Extract timestamp from FFmpeg output
                        pts_time = line.split('pts_time:')[1].split()[0]
                        scene_changes.append(float(pts_time))
                    except:
                        continue

            # Enhance segment timings with scene transition info
            enhanced_segments = []
            for segment in segment_timings:
                # Find nearest scene changes
                start_time = segment["start_time"]
                end_time = segment["end_time"]

                # Find scene changes within this segment
                segment_scenes = [sc for sc in scene_changes if start_time <= sc <= end_time]

                # Find nearest scene changes before and after
                before_scenes = [sc for sc in scene_changes if sc < start_time]
                after_scenes = [sc for sc in scene_changes if sc > end_time]

                nearest_before = max(before_scenes) if before_scenes else None
                nearest_after = min(after_scenes) if after_scenes else None

                enhanced_segment = {
                    **segment,
                    "scene_changes_within": segment_scenes,
                    "nearest_scene_before": nearest_before,
                    "nearest_scene_after": nearest_after,
                    "has_scene_transitions": len(segment_scenes) > 0
                }

                enhanced_segments.append(enhanced_segment)

            logger.info(f"Analyzed {len(scene_changes)} scene transitions")
            return enhanced_segments

        except Exception as e:
            logger.error(f"Scene transition analysis failed: {str(e)}")
            # Return original segments if analysis fails
            return segment_timings

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get detailed video information"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", video_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                info = json.loads(result.stdout)

                # Extract video stream info
                video_stream = None
                audio_stream = None

                for stream in info.get("streams", []):
                    if stream.get("codec_type") == "video":
                        video_stream = stream
                    elif stream.get("codec_type") == "audio":
                        audio_stream = stream

                return {
                    "duration": float(info.get("format", {}).get("duration", 0)),
                    "size": int(info.get("format", {}).get("size", 0)),
                    "bitrate": int(info.get("format", {}).get("bit_rate", 0)),
                    "video": video_stream,
                    "audio": audio_stream,
                    "format": info.get("format", {})
                }
            else:
                logger.error(f"FFprobe error: {result.stderr}")
                return {}

        except Exception as e:
            logger.error(f"Failed to get video info: {str(e)}")
            return {}
