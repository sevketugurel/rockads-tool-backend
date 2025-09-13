"""
Ensure selected countries exist in DB with reasonable defaults.

Run:
  python scripts/add_selected_countries.py JP CN KP CH
If no args given, adds all four.
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.database.models import Base, CountryModel
from core.config.settings import settings


DEFAULTS = {
    "JP": dict(
        country_code="JP", country_name="Japan", language_code="ja", language_name="Japanese",
        dialect_info={"primary_dialect": "Standard Japanese", "accent_characteristics": ["pitch accent"],
                      "common_phrases": {"how_are_you": "お元気ですか？", "goodbye": "またね", "thank_you": "ありがとうございます"},
                      "slang_terms": {}, "formality_level": "formal", "pronunciation_notes": []},
        cultural_context={"humor_style": "subtle", "communication_style": "indirect", "color_preferences": ["white","red"],
                          "taboo_topics": ["politics"], "cultural_values": ["harmony","craftsmanship"],
                          "marketing_preferences": "quality and precision", "call_to_action_style": "polite",
                          "urgency_indicators": ["今だけ"], "trust_building_elements": ["awards"]},
        preferred_voice_gender="neutral", speech_rate=0.95, speech_pitch=1.05, voice_characteristics=["polite"],
        timezone="Asia/Tokyo", currency="JPY", date_format="YYYY/MM/DD", number_format="1,234.56", priority=8,
    ),
    "CN": dict(
        country_code="CN", country_name="China", language_code="zh", language_name="Chinese (Mandarin)",
        dialect_info={"primary_dialect": "Mandarin", "accent_characteristics": ["tonal"],
                      "common_phrases": {"how_are_you": "你好吗？", "goodbye": "再见", "thank_you": "谢谢"},
                      "slang_terms": {}, "formality_level": "semi-formal", "pronunciation_notes": []},
        cultural_context={"humor_style": "situational", "communication_style": "contextual", "color_preferences": ["red","gold"],
                          "taboo_topics": ["sensitive politics"], "cultural_values": ["family","progress"],
                          "marketing_preferences": "value and practicality", "call_to_action_style": "clear",
                          "urgency_indicators": ["限时"], "trust_building_elements": ["certifications"]},
        preferred_voice_gender="neutral", speech_rate=1.0, speech_pitch=1.0, voice_characteristics=["confident"],
        timezone="Asia/Shanghai", currency="CNY", date_format="YYYY-MM-DD", number_format="1,234.56", priority=8,
    ),
    "KP": dict(
        country_code="KP", country_name="North Korea", language_code="ko", language_name="Korean",
        dialect_info={"primary_dialect": "Pyongyang", "accent_characteristics": [],
                      "common_phrases": {"how_are_you": "안녕하십니까?", "goodbye": "안녕히 계십시오", "thank_you": "감사합니다"},
                      "slang_terms": {}, "formality_level": "formal", "pronunciation_notes": []},
        cultural_context={"humor_style": "formal", "communication_style": "very formal", "color_preferences": ["red","blue"],
                          "taboo_topics": ["politics"], "cultural_values": ["collectivism"],
                          "marketing_preferences": "n/a", "call_to_action_style": "formal",
                          "urgency_indicators": [], "trust_building_elements": []},
        preferred_voice_gender="neutral", speech_rate=0.95, speech_pitch=1.0, voice_characteristics=["formal"],
        timezone="Asia/Pyongyang", currency="KPW", date_format="YYYY-MM-DD", number_format="1,234.56", priority=1,
    ),
    "CH": dict(
        country_code="CH", country_name="Switzerland", language_code="de", language_name="German (Switzerland)",
        dialect_info={"primary_dialect": "Swiss German", "accent_characteristics": ["alemannic"],
                      "common_phrases": {"how_are_you": "Wie gaht's?", "goodbye": "Ade", "thank_you": "Danke"},
                      "slang_terms": {}, "formality_level": "polite", "pronunciation_notes": []},
        cultural_context={"humor_style": "dry", "communication_style": "polite", "color_preferences": ["red","white"],
                          "taboo_topics": [], "cultural_values": ["precision","neutrality"],
                          "marketing_preferences": "quality and clarity", "call_to_action_style": "polite",
                          "urgency_indicators": ["solange Vorrat reicht"], "trust_building_elements": ["Swiss quality"]},
        preferred_voice_gender="neutral", speech_rate=0.98, speech_pitch=1.0, voice_characteristics=["clear"],
        timezone="Europe/Zurich", currency="CHF", date_format="DD.MM.YYYY", number_format="1'234.56", priority=7,
    ),
}


def ensure_codes(codes):
    engine = create_engine(settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = SessionLocal()
    try:
        for code in codes:
            code = code.upper()
            d = DEFAULTS.get(code)
            if not d:
                print(f"No defaults for {code}, skipping")
                continue
            existing = s.query(CountryModel).filter(CountryModel.country_code == code).first()
            if existing:
                print(f"{code} already exists: {existing.country_name}")
                continue
            s.add(CountryModel(**d))
            s.commit()
            print(f"Added {code}")
    finally:
        s.close()


if __name__ == "__main__":
    codes = sys.argv[1:] or ["JP", "CN", "KP", "CH"]
    ensure_codes(codes)

