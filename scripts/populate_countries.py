"""
Script to populate the countries table with sample data for testing localization
"""
import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.database.models import Base, CountryModel
from core.config.settings import settings


def create_sample_countries():
    """Create sample countries with cultural context for testing"""

    countries_data = [
        {
            "country_code": "US",
            "country_name": "United States",
            "language_code": "en",
            "language_name": "English (US)",
            "dialect_info": {
                "primary_dialect": "General American",
                "accent_characteristics": ["rhotic", "broad vowels", "clear consonants"],
                "common_phrases": {
                    "how_are_you": "How are you doing?",
                    "goodbye": "Have a great day!",
                    "thank_you": "Thank you so much!"
                },
                "slang_terms": {
                    "awesome": "really great",
                    "cool": "good/interesting",
                    "totally": "completely"
                },
                "formality_level": "casual",
                "pronunciation_notes": ["Clear R sounds", "Dropped T in some words"]
            },
            "cultural_context": {
                "humor_style": "direct",
                "communication_style": "direct",
                "color_preferences": ["blue", "red", "white", "gold"],
                "taboo_topics": ["politics in workplace", "personal finances", "religion"],
                "cultural_values": ["individualism", "achievement", "innovation", "freedom"],
                "marketing_preferences": "direct benefits, competitive pricing, testimonials",
                "call_to_action_style": "urgent and direct",
                "urgency_indicators": ["limited time", "act now", "don't miss out", "while supplies last"],
                "trust_building_elements": ["reviews", "guarantees", "certifications", "testimonials"]
            },
            "preferred_voice_gender": "neutral",
            "speech_rate": 1.0,
            "speech_pitch": 1.0,
            "voice_characteristics": ["confident", "friendly", "energetic"],
            "timezone": "America/New_York",
            "currency": "USD",
            "date_format": "MM/DD/YYYY",
            "number_format": "1,234.56",
            "priority": 10
        },
        {
            "country_code": "GB",
            "country_name": "United Kingdom",
            "language_code": "en",
            "language_name": "English (UK)",
            "dialect_info": {
                "primary_dialect": "Received Pronunciation",
                "accent_characteristics": ["non-rhotic", "precise articulation", "clipped consonants"],
                "common_phrases": {
                    "how_are_you": "How are you getting on?",
                    "goodbye": "Cheerio!",
                    "thank_you": "Cheers!"
                },
                "slang_terms": {
                    "brilliant": "excellent",
                    "proper": "very/really",
                    "cheers": "thank you"
                },
                "formality_level": "semi-formal",
                "pronunciation_notes": ["Dropped R at end of words", "Long A sounds"]
            },
            "cultural_context": {
                "humor_style": "dry",
                "communication_style": "indirect",
                "color_preferences": ["navy", "burgundy", "forest green", "gold"],
                "taboo_topics": ["personal income", "overly emotional displays", "excessive self-promotion"],
                "cultural_values": ["tradition", "politeness", "understatement", "queue etiquette"],
                "marketing_preferences": "understated elegance, heritage, quality over quantity",
                "call_to_action_style": "polite suggestion",
                "urgency_indicators": ["whilst stocks last", "for a limited period", "don't delay"],
                "trust_building_elements": ["heritage", "royal warrants", "quality marks", "recommendations"]
            },
            "preferred_voice_gender": "neutral",
            "speech_rate": 0.95,
            "speech_pitch": 0.98,
            "voice_characteristics": ["sophisticated", "articulate", "measured"],
            "timezone": "Europe/London",
            "currency": "GBP",
            "date_format": "DD/MM/YYYY",
            "number_format": "1,234.56",
            "priority": 9
        },
        {
            "country_code": "AU",
            "country_name": "Australia",
            "language_code": "en",
            "language_name": "English (Australian)",
            "dialect_info": {
                "primary_dialect": "General Australian",
                "accent_characteristics": ["rising intonation", "vowel shifts", "casual delivery"],
                "common_phrases": {
                    "how_are_you": "How ya going?",
                    "goodbye": "See ya later!",
                    "thank_you": "Cheers mate!"
                },
                "slang_terms": {
                    "mate": "friend",
                    "no worries": "you're welcome",
                    "fair dinkum": "genuine/true"
                },
                "formality_level": "casual",
                "pronunciation_notes": ["Rising intonation at end of statements", "Shortened vowels"]
            },
            "cultural_context": {
                "humor_style": "self-deprecating",
                "communication_style": "casual",
                "color_preferences": ["green", "gold", "blue", "red"],
                "taboo_topics": ["tall poppy syndrome", "overly formal behavior"],
                "cultural_values": ["mateship", "fair go", "laid-back attitude", "outdoor lifestyle"],
                "marketing_preferences": "authentic, down-to-earth, outdoor lifestyle",
                "call_to_action_style": "friendly invitation",
                "urgency_indicators": ["don't miss out", "limited time", "get in quick"],
                "trust_building_elements": ["word of mouth", "local recommendations", "Aussie made"]
            },
            "preferred_voice_gender": "neutral",
            "speech_rate": 1.05,
            "speech_pitch": 1.02,
            "voice_characteristics": ["friendly", "relaxed", "approachable"],
            "timezone": "Australia/Sydney",
            "currency": "AUD",
            "date_format": "DD/MM/YYYY",
            "number_format": "1,234.56",
            "priority": 8
        },
        {
            "country_code": "DE",
            "country_name": "Germany",
            "language_code": "de",
            "language_name": "German",
            "dialect_info": {
                "primary_dialect": "Hochdeutsch",
                "accent_characteristics": ["precise consonants", "guttural sounds", "clear articulation"],
                "common_phrases": {
                    "how_are_you": "Wie geht es Ihnen?",
                    "goodbye": "Auf Wiedersehen!",
                    "thank_you": "Vielen Dank!"
                },
                "slang_terms": {
                    "super": "great",
                    "krass": "crazy/intense",
                    "geil": "awesome"
                },
                "formality_level": "formal",
                "pronunciation_notes": ["Strong consonants", "Umlauts important", "Word stress patterns"]
            },
            "cultural_context": {
                "humor_style": "dry",
                "communication_style": "direct",
                "color_preferences": ["black", "red", "gold", "blue"],
                "taboo_topics": ["WWII references", "personal finances", "work-life balance criticism"],
                "cultural_values": ["efficiency", "punctuality", "quality", "environmental consciousness"],
                "marketing_preferences": "technical specifications, quality assurance, environmental benefits",
                "call_to_action_style": "clear and logical",
                "urgency_indicators": ["begrenzte Zeit", "jetzt handeln", "solange Vorrat reicht"],
                "trust_building_elements": ["technical certifications", "made in Germany", "engineering excellence"]
            },
            "preferred_voice_gender": "neutral",
            "speech_rate": 0.92,
            "speech_pitch": 0.96,
            "voice_characteristics": ["authoritative", "precise", "clear"],
            "timezone": "Europe/Berlin",
            "currency": "EUR",
            "date_format": "DD.MM.YYYY",
            "number_format": "1.234,56",
            "priority": 7
        },
        {
            "country_code": "ES",
            "country_name": "Spain",
            "language_code": "es",
            "language_name": "Spanish (Spain)",
            "dialect_info": {
                "primary_dialect": "Castilian Spanish",
                "accent_characteristics": ["theta sound", "clear vowels", "rolling Rs"],
                "common_phrases": {
                    "how_are_you": "¿Qué tal estás?",
                    "goodbye": "¡Hasta luego!",
                    "thank_you": "¡Muchas gracias!"
                },
                "slang_terms": {
                    "guay": "cool",
                    "chulo": "cool/nice",
                    "flipar": "to be amazed"
                },
                "formality_level": "semi-formal",
                "pronunciation_notes": ["Lisp on C and Z", "Clear vowel sounds", "Silent H"]
            },
            "cultural_context": {
                "humor_style": "animated",
                "communication_style": "expressive",
                "color_preferences": ["red", "yellow", "orange", "blue"],
                "taboo_topics": ["regional politics", "bullfighting criticism", "siesta stereotypes"],
                "cultural_values": ["family", "social connections", "passion", "tradition"],
                "marketing_preferences": "emotional appeal, family focus, social proof",
                "call_to_action_style": "passionate and enthusiastic",
                "urgency_indicators": ["tiempo limitado", "no te lo pierdas", "oferta especial"],
                "trust_building_elements": ["family recommendations", "local presence", "tradition"]
            },
            "preferred_voice_gender": "neutral",
            "speech_rate": 1.1,
            "speech_pitch": 1.05,
            "voice_characteristics": ["warm", "expressive", "passionate"],
            "timezone": "Europe/Madrid",
            "currency": "EUR",
            "date_format": "DD/MM/YYYY",
            "number_format": "1.234,56",
            "priority": 6
        }
    ]

    return countries_data


def main():
    """Main function to populate countries"""
    # Create database engine
    engine = create_engine(settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))

    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        # Get sample data
        countries_data = create_sample_countries()

        # Check if countries already exist
        existing_count = session.query(CountryModel).count()
        if existing_count > 0:
            print(f"Countries table already has {existing_count} entries. Skipping population.")
            return

        # Create country entries
        for country_data in countries_data:
            country = CountryModel(**country_data)
            session.add(country)

        # Commit changes
        session.commit()
        print(f"Successfully populated {len(countries_data)} countries.")

        # Display created countries
        countries = session.query(CountryModel).all()
        print("\nCreated countries:")
        for country in countries:
            print(f"- {country.country_code}: {country.country_name} ({country.language_name})")

    except Exception as e:
        session.rollback()
        print(f"Error populating countries: {str(e)}")
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()