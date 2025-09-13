from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TranslationStatus(str, Enum):
    PENDING = "pending"
    ANALYZING_CONTEXT = "analyzing_context"
    TRANSLATING = "translating"
    CULTURAL_ADAPTATION = "cultural_adaptation"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoSceneContext(BaseModel):
    """Context extracted from video scenes for better translation"""
    timestamp: float  # When this scene occurs
    visual_elements: List[str]  # Objects, people, settings visible
    emotions: List[str]  # Emotions detected in faces/body language
    actions: List[str]  # Actions happening in the scene
    setting_type: str  # indoor, outdoor, office, home, etc.
    brand_elements: List[str]  # Logos, products, brand colors visible
    text_overlays: List[str]  # Any text visible in the video
    color_palette: List[str]  # Dominant colors in the scene


class CulturalAdaptation(BaseModel):
    """Cultural adaptations made to the translation"""
    original_concept: str  # Original advertising concept
    adapted_concept: str  # How it was adapted for the target culture
    changes_made: List[str]  # List of specific changes
    cultural_reasoning: str  # Why these changes were necessary
    risk_assessment: str  # Potential cultural risks identified
    effectiveness_score: float  # Predicted effectiveness (0-1)


class TranslationSegment(BaseModel):
    """Individual translation segment with context"""
    start_time: float
    end_time: float
    original_text: str
    translated_text: str
    confidence_score: float
    context_used: List[str]  # Which contexts influenced this translation
    cultural_adaptations: List[str]  # Specific adaptations made
    scene_context: Optional[VideoSceneContext] = None


class Translation(BaseModel):
    """Enhanced translation entity with video and cultural context"""
    id: Optional[int] = None
    video_id: int
    transcription_id: int
    country_id: int  # Target country for localization

    # Translation details
    source_language: str  # ISO 639-1 code
    target_language: str  # ISO 639-1 code
    country_code: str  # ISO 3166-1 alpha-2 code

    # Status and progress
    status: TranslationStatus = TranslationStatus.PENDING
    progress_percentage: float = 0.0

    # Translation content
    segments: List[TranslationSegment] = []
    full_translated_text: Optional[str] = None

    # Context and analysis
    video_analysis: Dict[str, Any] = {}  # Overall video analysis from Gemini
    advertising_context: Dict[str, Any] = {}  # Detected ad elements and intent
    cultural_adaptation: Optional[CulturalAdaptation] = None

    # Quality metrics
    overall_confidence: Optional[float] = None
    cultural_appropriateness_score: Optional[float] = None
    brand_consistency_score: Optional[float] = None
    effectiveness_prediction: Optional[float] = None

    # Processing details
    model_used: str = "gemini-2.0-flash-exp"
    processing_time: Optional[float] = None
    tokens_used: Optional[int] = None

    # Error handling
    error_message: Optional[str] = None
    warnings: List[str] = []

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        use_enum_values = True


class TranslationJob(BaseModel):
    """Batch translation job for multiple countries"""
    id: Optional[int] = None
    video_id: int
    user_id: Optional[int] = None

    # Job configuration
    target_countries: List[int]  # List of country IDs
    preserve_brand_elements: bool = True
    adapt_for_culture: bool = True
    maintain_video_timing: bool = True

    # Processing settings
    analysis_depth: str = "comprehensive"  # basic, standard, comprehensive
    cultural_sensitivity: str = "high"  # low, medium, high
    brand_consistency: str = "strict"  # flexible, balanced, strict

    # Progress tracking
    status: str = "created"  # created, processing, completed, failed
    progress_percentage: float = 0.0
    translations: List[int] = []  # Translation IDs

    # Results
    total_processing_time: Optional[float] = None
    success_count: int = 0
    failure_count: int = 0

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True