from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TranscriptionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptionSegment(BaseModel):
    """Individual segment of transcription with timing information"""
    start_time: float  # seconds
    end_time: float    # seconds
    text: str
    confidence: Optional[float] = None
    speaker_id: Optional[str] = None


class Transcription(BaseModel):
    id: Optional[int] = None
    video_id: int
    status: TranscriptionStatus = TranscriptionStatus.PENDING
    language_code: str  # ISO 639-1 language code (e.g., 'en', 'es', 'tr')
    full_text: Optional[str] = None
    segments: Optional[List[TranscriptionSegment]] = []
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None  # seconds
    model_used: str = "gemini-2.5-pro"
    extra_metadata: Optional[Dict[str, Any]] = None  # Additional data from Gemini
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        use_enum_values = True