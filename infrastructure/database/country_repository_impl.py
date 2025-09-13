import json
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from domain.entities.country import Country, DialectInfo, CulturalContext
from domain.repositories.country_repository import CountryRepository
from infrastructure.database.models import CountryModel


class CountryRepositoryImpl(CountryRepository):
    """SQLAlchemy implementation of CountryRepository"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create(self, country: Country) -> Country:
        """Create a new country"""
        db_country = CountryModel(
            country_code=country.country_code,
            country_name=country.country_name,
            language_code=country.language_code,
            language_name=country.language_name,
            dialect_info=country.dialect_info.dict() if country.dialect_info else {},
            cultural_context=country.cultural_context.dict() if country.cultural_context else {},
            preferred_voice_gender=country.preferred_voice_gender,
            speech_rate=country.speech_rate,
            speech_pitch=country.speech_pitch,
            voice_characteristics=country.voice_characteristics,
            timezone=country.timezone,
            currency=country.currency,
            date_format=country.date_format,
            number_format=country.number_format,
            text_direction=country.text_direction,
            character_encoding=country.character_encoding,
            is_active=country.is_active,
            priority=country.priority
        )

        self.db.add(db_country)
        await self.db.commit()
        await self.db.refresh(db_country)

        return self._to_entity(db_country)

    async def get_by_id(self, country_id: int) -> Optional[Country]:
        """Get country by ID"""
        result = await self.db.execute(select(CountryModel).where(CountryModel.id == country_id))
        db_country = result.scalar_one_or_none()
        return self._to_entity(db_country) if db_country else None

    async def get_by_country_code(self, country_code: str) -> Optional[Country]:
        """Get country by country code"""
        result = await self.db.execute(
            select(CountryModel).where(CountryModel.country_code == country_code.upper())
        )
        db_country = result.scalar_one_or_none()
        return self._to_entity(db_country) if db_country else None

    async def get_by_country_codes(self, country_codes: List[str]) -> List[Country]:
        """Get multiple countries by country codes"""
        upper_codes = [code.upper() for code in country_codes]
        result = await self.db.execute(
            select(CountryModel).where(CountryModel.country_code.in_(upper_codes))
        )
        db_countries = result.scalars().all()
        return [self._to_entity(db_country) for db_country in db_countries]

    async def get_by_language_code(self, language_code: str) -> List[Country]:
        """Get countries by language code"""
        result = await self.db.execute(
            select(CountryModel).where(CountryModel.language_code == language_code.lower())
        )
        db_countries = result.scalars().all()
        return [self._to_entity(db_country) for db_country in db_countries]

    async def get_all(self) -> List[Country]:
        """Get all countries"""
        result = await self.db.execute(select(CountryModel))
        db_countries = result.scalars().all()
        return [self._to_entity(db_country) for db_country in db_countries]

    async def get_all_active(self) -> List[Country]:
        """Get all active countries"""
        result = await self.db.execute(
            select(CountryModel)
            .where(CountryModel.is_active == True)
            .order_by(CountryModel.priority.desc(), CountryModel.country_name)
        )
        db_countries = result.scalars().all()
        return [self._to_entity(db_country) for db_country in db_countries]

    async def update(self, country: Country) -> Country:
        """Update existing country"""
        result = await self.db.execute(
            select(CountryModel).where(CountryModel.id == country.id)
        )
        db_country = result.scalar_one_or_none()
        if not db_country:
            raise ValueError(f"Country with ID {country.id} not found")

        # Update fields
        db_country.country_code = country.country_code
        db_country.country_name = country.country_name
        db_country.language_code = country.language_code
        db_country.language_name = country.language_name
        db_country.dialect_info = country.dialect_info.dict() if country.dialect_info else {}
        db_country.cultural_context = country.cultural_context.dict() if country.cultural_context else {}
        db_country.preferred_voice_gender = country.preferred_voice_gender
        db_country.speech_rate = country.speech_rate
        db_country.speech_pitch = country.speech_pitch
        db_country.voice_characteristics = country.voice_characteristics
        db_country.timezone = country.timezone
        db_country.currency = country.currency
        db_country.date_format = country.date_format
        db_country.number_format = country.number_format
        db_country.text_direction = country.text_direction
        db_country.character_encoding = country.character_encoding
        db_country.is_active = country.is_active
        db_country.priority = country.priority

        await self.db.commit()
        await self.db.refresh(db_country)

        return self._to_entity(db_country)

    async def delete(self, country_id: int) -> bool:
        """Delete country by ID"""
        result = await self.db.execute(
            select(CountryModel).where(CountryModel.id == country_id)
        )
        db_country = result.scalar_one_or_none()
        if not db_country:
            return False

        await self.db.delete(db_country)
        await self.db.commit()
        return True

    async def search_by_name(self, name_pattern: str) -> List[Country]:
        """Search countries by name pattern"""
        result = await self.db.execute(
            select(CountryModel).where(CountryModel.country_name.ilike(f"%{name_pattern}%"))
        )
        db_countries = result.scalars().all()
        return [self._to_entity(db_country) for db_country in db_countries]

    def _to_entity(self, db_country: CountryModel) -> Country:
        """Convert database model to domain entity"""
        if not db_country:
            return None

        # Parse JSON fields
        dialect_info = DialectInfo(**db_country.dialect_info) if db_country.dialect_info else DialectInfo(
            primary_dialect="standard",
            accent_characteristics=[],
            common_phrases={},
            slang_terms={},
            formality_level="neutral",
            pronunciation_notes=[]
        )

        cultural_context = CulturalContext(**db_country.cultural_context) if db_country.cultural_context else CulturalContext(
            humor_style="neutral",
            communication_style="direct",
            color_preferences=[],
            taboo_topics=[],
            cultural_values=[],
            marketing_preferences="standard",
            call_to_action_style="direct",
            urgency_indicators=[],
            trust_building_elements=[]
        )

        return Country(
            id=db_country.id,
            country_code=db_country.country_code,
            country_name=db_country.country_name,
            language_code=db_country.language_code,
            language_name=db_country.language_name,
            dialect_info=dialect_info,
            cultural_context=cultural_context,
            preferred_voice_gender=db_country.preferred_voice_gender,
            speech_rate=db_country.speech_rate,
            speech_pitch=db_country.speech_pitch,
            voice_characteristics=db_country.voice_characteristics or [],
            timezone=db_country.timezone,
            currency=db_country.currency,
            date_format=db_country.date_format,
            number_format=db_country.number_format,
            text_direction=db_country.text_direction,
            character_encoding=db_country.character_encoding,
            is_active=db_country.is_active,
            priority=db_country.priority,
            created_at=db_country.created_at,
            updated_at=db_country.updated_at
        )