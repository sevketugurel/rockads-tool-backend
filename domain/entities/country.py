from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class CulturalContext(BaseModel):
    """Cultural context information for advertising localization"""
    humor_style: str  # dry, slapstick, wordplay, sarcasm, etc.
    communication_style: str  # direct, indirect, formal, casual
    color_preferences: List[str]  # Colors that work well in the culture
    taboo_topics: List[str]  # Topics to avoid
    cultural_values: List[str]  # Important cultural values
    marketing_preferences: str  # How marketing typically works in this culture
    call_to_action_style: str  # How CTAs should be phrased
    urgency_indicators: List[str]  # Words/phrases that create urgency
    trust_building_elements: List[str]  # What builds trust in advertising


class DialectInfo(BaseModel):
    """Dialect and accent information for a country"""
    primary_dialect: str  # Main dialect/accent name
    accent_characteristics: List[str]  # Key accent features
    common_phrases: Dict[str, str]  # Common phrases unique to this country
    slang_terms: Dict[str, str]  # Local slang and their meanings
    formality_level: str  # formal, semi-formal, casual
    pronunciation_notes: List[str]  # Special pronunciation considerations


class Country(BaseModel):
    """Country entity with comprehensive localization context"""
    id: Optional[int] = None
    country_code: str  # ISO 3166-1 alpha-2 code (US, GB, AU, etc.)
    country_name: str  # Full country name
    language_code: str  # Primary language ISO 639-1 code
    language_name: str  # Language display name

    # Cultural and linguistic context
    dialect_info: DialectInfo
    cultural_context: CulturalContext

    # Voice and speech configuration
    preferred_voice_gender: str = "neutral"  # male, female, neutral
    speech_rate: float = 1.0  # Normal speed multiplier
    speech_pitch: float = 1.0  # Normal pitch multiplier
    voice_characteristics: List[str] = []  # warm, authoritative, friendly, etc.

    # Market-specific information
    timezone: str  # Primary timezone
    currency: str  # Local currency code
    date_format: str  # Preferred date format
    number_format: str  # Number formatting preferences

    # Technical settings
    text_direction: str = "ltr"  # ltr, rtl
    character_encoding: str = "utf-8"

    # Metadata
    is_active: bool = True
    priority: int = 0  # For ordering in UI
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True