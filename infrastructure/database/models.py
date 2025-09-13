from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class VideoStatusEnum(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    TRANSCRIBED = "transcribed"
    TRANSLATED = "translated"
    LOCALIZED = "localized"
    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptionStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LocalizationJobStatusEnum(str, enum.Enum):
    CREATED = "created"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    GENERATING_SPEECH = "generating_speech"
    PROCESSING_VIDEO = "processing_video"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TranslationStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ANALYZING_CONTEXT = "analyzing_context"
    TRANSLATING = "translating"
    CULTURAL_ADAPTATION = "cultural_adaptation"
    COMPLETED = "completed"
    FAILED = "failed"


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("ItemModel", back_populates="user")


class ItemModel(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("UserModel", back_populates="items")


class VideoModel(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    duration = Column(Float, nullable=True)
    status = Column(Enum(VideoStatusEnum), default=VideoStatusEnum.UPLOADED, nullable=False)
    content_type = Column(String(100), nullable=False)
    language = Column(String(10), nullable=True)  # ISO 639-1 language code
    description = Column(Text, nullable=True)
    is_advertisement = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transcriptions = relationship("TranscriptionModel", back_populates="video", cascade="all, delete-orphan")
    localization_jobs = relationship("LocalizationJobModel", back_populates="video", cascade="all, delete-orphan")


class TranscriptionModel(Base):
    __tablename__ = "transcriptions"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    status = Column(Enum(TranscriptionStatusEnum), default=TranscriptionStatusEnum.PENDING, nullable=False)
    language_code = Column(String(10), nullable=False)
    full_text = Column(Text, nullable=True)
    segments = Column(JSON, nullable=True)  # Store segments as JSON
    confidence_score = Column(Float, nullable=True)
    processing_time = Column(Float, nullable=True)
    model_used = Column(String(100), default="gemini-2.5-pro")
    extra_metadata = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    video = relationship("VideoModel", back_populates="transcriptions")


class LocalizationJobModel(Base):
    __tablename__ = "localization_jobs"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(LocalizationJobStatusEnum), default=LocalizationJobStatusEnum.CREATED, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_languages = Column(JSON, nullable=False)  # List of target languages with configuration
    # Selected target countries for this job
    target_countries = Column(JSON, nullable=True)

    # Workflow tracking
    transcription_id = Column(Integer, ForeignKey("transcriptions.id"), nullable=True)
    translation_ids = Column(JSON, nullable=True)  # List of translation IDs
    audio_generation_ids = Column(JSON, nullable=True)  # List of audio generation IDs
    output_video_ids = Column(JSON, nullable=True)  # List of final video IDs

    # Configuration
    preserve_timing = Column(Boolean, default=True)
    adjust_for_culture = Column(Boolean, default=True)
    voice_tone = Column(String(50), default="professional")

    # Progress and metadata
    progress_percentage = Column(Float, default=0.0)
    estimated_completion = Column(DateTime, nullable=True)
    total_processing_time = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    video = relationship("VideoModel", back_populates="localization_jobs")
    user = relationship("UserModel")
    transcription = relationship("TranscriptionModel")


class CountryModel(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)
    country_code = Column(String(2), unique=True, index=True, nullable=False)  # ISO 3166-1 alpha-2
    country_name = Column(String(100), nullable=False)
    language_code = Column(String(10), nullable=False)  # ISO 639-1
    language_name = Column(String(50), nullable=False)

    # Dialect and cultural information stored as JSON
    dialect_info = Column(JSON, nullable=False)
    cultural_context = Column(JSON, nullable=False)

    # Voice and speech settings
    preferred_voice_gender = Column(String(10), default="neutral")
    speech_rate = Column(Float, default=1.0)
    speech_pitch = Column(Float, default=1.0)
    voice_characteristics = Column(JSON, nullable=True)

    # Market-specific information
    timezone = Column(String(50), nullable=True)
    currency = Column(String(10), nullable=True)
    date_format = Column(String(20), nullable=True)
    number_format = Column(String(20), nullable=True)

    # Technical settings
    text_direction = Column(String(10), default="ltr")
    character_encoding = Column(String(20), default="utf-8")

    # Metadata
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    translations = relationship("TranslationModel", back_populates="country")


class TranslationModel(Base):
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    transcription_id = Column(Integer, ForeignKey("transcriptions.id"), nullable=False)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)

    # Language and country information
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    country_code = Column(String(2), nullable=False)

    # Status and progress
    status = Column(Enum(TranslationStatusEnum), default=TranslationStatusEnum.PENDING, nullable=False)
    progress_percentage = Column(Float, default=0.0)

    # Translation content
    segments = Column(JSON, nullable=True)  # List of translation segments
    full_translated_text = Column(Text, nullable=True)

    # Context and analysis
    video_analysis = Column(JSON, nullable=True)  # Video analysis results
    advertising_context = Column(JSON, nullable=True)  # Advertising context
    cultural_adaptation = Column(JSON, nullable=True)  # Cultural adaptation details

    # Quality metrics
    overall_confidence = Column(Float, nullable=True)
    cultural_appropriateness_score = Column(Float, nullable=True)
    brand_consistency_score = Column(Float, nullable=True)
    effectiveness_prediction = Column(Float, nullable=True)

    # Processing details
    model_used = Column(String(100), default="gemini-2.0-flash-exp")
    processing_time = Column(Float, nullable=True)
    tokens_used = Column(Integer, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    warnings = Column(JSON, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    video = relationship("VideoModel")
    transcription = relationship("TranscriptionModel")
    country = relationship("CountryModel", back_populates="translations")


class TranslationJobModel(Base):
    __tablename__ = "translation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Job configuration
    target_countries = Column(JSON, nullable=False)  # List of country IDs
    preserve_brand_elements = Column(Boolean, default=True)
    adapt_for_culture = Column(Boolean, default=True)
    maintain_video_timing = Column(Boolean, default=True)

    # Processing settings
    analysis_depth = Column(String(20), default="comprehensive")
    cultural_sensitivity = Column(String(10), default="high")
    brand_consistency = Column(String(10), default="strict")

    # Progress tracking
    status = Column(String(20), default="created")
    progress_percentage = Column(Float, default=0.0)
    translations = Column(JSON, nullable=True)  # List of translation IDs

    # Results
    total_processing_time = Column(Float, nullable=True)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    video = relationship("VideoModel")
    user = relationship("UserModel")
