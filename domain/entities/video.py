from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class VideoStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    TRANSCRIBED = "transcribed"
    TRANSLATED = "translated"
    LOCALIZED = "localized"
    COMPLETED = "completed"
    FAILED = "failed"


class Video(BaseModel):
    id: Optional[int] = None
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    duration: Optional[float] = None
    status: VideoStatus = VideoStatus.UPLOADED
    content_type: str
    language: Optional[str] = None  # Original language detected
    description: Optional[str] = None
    is_advertisement: bool = True  # Defaulting to advertisement context
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        use_enum_values = True