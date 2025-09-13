import os
import platform
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from domain.entities.translation import TranslationSegment

logger = logging.getLogger(__name__)


class LocalTTSService:
    """Offline/OS-native TTS fallback.

    - macOS: uses `say`
    - Linux: uses `espeak` (if available)
    - Windows: not supported (returns empty list)

    Output format may be AIFF/WAV depending on backend; ffmpeg can read both.
    """

    def __init__(self):
        self.system = platform.system().lower()
        self.available = self._detect_backend()

    def _detect_backend(self) -> Optional[str]:
        def _has(cmd: str) -> bool:
            from shutil import which
            return which(cmd) is not None

        if self.system == "darwin" and _has("say"):
            return "say"
        if self.system == "linux" and _has("espeak"):
            return "espeak"
        return None

    async def generate_speech_for_segments(
        self,
        segments: List[TranslationSegment],
        target_language: str,
        country_code: str,
        output_dir: str
    ) -> List[Dict[str, Any]]:
        """Generate audio files for each segment using local TTS.

        Returns list of dicts with keys: start_time, end_time, duration, audio_file
        """
        if not self.available:
            logger.warning("Local TTS backend not available on this system")
            return []

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        audio_segments: List[Dict[str, Any]] = []

        for i, seg in enumerate(segments):
            try:
                text = seg.translated_text or seg.original_text or ""
                if not text.strip():
                    continue

                duration = max(0.1, float(seg.end_time) - float(seg.start_time))

                # Estimate rate to fit duration
                words = max(1, len(text.split()))
                target_wpm = int(min(300, max(90, (words / duration) * 60)))

                if self.available == "say":
                    # macOS 'say' outputs AIFF; convert to .aiff
                    outfile = out_dir / f"seg_{i:03d}.aiff"
                    cmd = [
                        "say",
                        "-r",
                        str(target_wpm),
                        "-o",
                        str(outfile),
                        text,
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.error(f"say failed for segment {i}: {result.stderr}")
                        continue
                elif self.available == "espeak":
                    # Linux espeak produces WAV via -w
                    outfile = out_dir / f"seg_{i:03d}.wav"
                    cmd = [
                        "espeak",
                        "-s",
                        str(target_wpm),
                        "-w",
                        str(outfile),
                        text,
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.error(f"espeak failed for segment {i}: {result.stderr}")
                        continue
                else:
                    # Unsupported OS
                    continue

                audio_segments.append(
                    {
                        "start_time": float(seg.start_time),
                        "end_time": float(seg.end_time),
                        "duration": duration,
                        "audio_file": str(outfile),
                    }
                )
            except Exception as e:
                logger.error(f"Local TTS failed for segment {i}: {e}")
                continue

        logger.info(f"Local TTS generated {len(audio_segments)} segments using {self.available}")
        return audio_segments

