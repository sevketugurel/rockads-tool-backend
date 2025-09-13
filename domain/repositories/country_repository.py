from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.country import Country


class CountryRepository(ABC):
    """Abstract repository for Country entities"""

    @abstractmethod
    async def create(self, country: Country) -> Country:
        """Create a new country"""
        pass

    @abstractmethod
    async def get_by_id(self, country_id: int) -> Optional[Country]:
        """Get country by ID"""
        pass

    @abstractmethod
    async def get_by_country_code(self, country_code: str) -> Optional[Country]:
        """Get country by country code (e.g., 'US', 'GB')"""
        pass

    @abstractmethod
    async def get_by_country_codes(self, country_codes: List[str]) -> List[Country]:
        """Get multiple countries by country codes"""
        pass

    @abstractmethod
    async def get_by_language_code(self, language_code: str) -> List[Country]:
        """Get countries by language code (e.g., 'en')"""
        pass

    @abstractmethod
    async def get_all(self) -> List[Country]:
        """Get all countries"""
        pass

    @abstractmethod
    async def get_all_active(self) -> List[Country]:
        """Get all active countries"""
        pass

    @abstractmethod
    async def update(self, country: Country) -> Country:
        """Update existing country"""
        pass

    @abstractmethod
    async def delete(self, country_id: int) -> bool:
        """Delete country by ID"""
        pass

    @abstractmethod
    async def search_by_name(self, name_pattern: str) -> List[Country]:
        """Search countries by name pattern"""
        pass