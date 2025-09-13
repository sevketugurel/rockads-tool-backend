from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class LocalizationJobStatus(str, Enum):
    CREATED = "created"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    GENERATING_SPEECH = "generating_speech"
    PROCESSING_VIDEO = "processing_video"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TargetLanguage(BaseModel):
    """Target language configuration for localization"""
    language_code: str  # ISO 639-1 code
    language_name: str  # Human readable name
    voice_id: Optional[str] = None  # ElevenLabs voice ID
    voice_settings: Optional[Dict[str, Any]] = None
    cultural_notes: Optional[str] = None


class LocalizationJob(BaseModel):
    """Main entity that orchestrates the entire video localization workflow"""
    id: Optional[int] = None
    video_id: int
    user_id: Optional[int] = None  # User who initiated the job
    status: LocalizationJobStatus = LocalizationJobStatus.CREATED
    source_language: str  # Original language
    target_languages: List[TargetLanguage]
    # Selected target countries (by Country.id)
    target_countries: List[int] = []

    # Workflow tracking
    transcription_id: Optional[int] = None
    translation_ids: Optional[List[int]] = []  # Multiple translations for different languages
    audio_generation_ids: Optional[List[int]] = []  # Generated audio files
    output_video_ids: Optional[List[int]] = []  # Final localized videos

    # Configuration
    preserve_timing: bool = True  # Preserve original timing
    adjust_for_culture: bool = True  # Apply cultural adaptations for ads
    voice_tone: str = "professional"  # professional, casual, energetic, etc.

    # Progress and metadata
    progress_percentage: float = 0.0
    estimated_completion: Optional[datetime] = None
    total_processing_time: Optional[float] = None
    error_details: Optional[List[str]] = []

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        use_enum_values = True
