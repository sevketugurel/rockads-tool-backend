"""
Ensure Turkey (TR) exists in the countries table.

Run:
  python scripts/add_tr_country.py
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from infrastructure.database.models import Base, CountryModel
from core.config.settings import settings


def ensure_tr():
    engine = create_engine(settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        existing = session.query(CountryModel).filter(CountryModel.country_code == "TR").first()
        if existing:
            print("TR already exists: ", existing.country_name)
            return

        tr = CountryModel(
            country_code="TR",
            country_name="Turkey",
            language_code="tr",
            language_name="Turkish",
            dialect_info={
                "primary_dialect": "Istanbul Turkish",
                "accent_characteristics": ["clear vowels", "soft g (ğ) elongation"],
                "common_phrases": {"how_are_you": "Nasılsın?", "goodbye": "Görüşürüz", "thank_you": "Teşekkürler"},
                "slang_terms": {"harika": "awesome", "süper": "great", "aynen": "exactly/agree"},
                "formality_level": "balanced",
                "pronunciation_notes": ["Ü/Ö rounded vowels", "Soft g elongates preceding vowel"],
            },
            cultural_context={
                "humor_style": "warm",
                "communication_style": "relational",
                "color_preferences": ["turquoise", "red", "gold", "white"],
                "taboo_topics": ["sensitive politics", "religion debates", "overly direct criticism"],
                "cultural_values": ["family", "hospitality", "respect", "community"],
                "marketing_preferences": "benefit + trust, local references, social proof",
                "call_to_action_style": "clear and friendly",
                "urgency_indicators": ["son gün", "kaçırma", "hemen başla"],
                "trust_building_elements": ["yerel referanslar", "garanti", "iade politikası"],
            },
            preferred_voice_gender="neutral",
            speech_rate=1.0,
            speech_pitch=1.0,
            voice_characteristics=["samimi", "anlaşılır", "doğal"],
            timezone="Europe/Istanbul",
            currency="TRY",
            date_format="DD.MM.YYYY",
            number_format="1.234,56",
            priority=8,
        )
        session.add(tr)
        session.commit()
        print("Added TR (Turkey) to countries table.")
    except Exception as e:
        session.rollback()
        print("Failed to add TR:", e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    ensure_tr()

