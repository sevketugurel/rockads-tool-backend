from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    app_name: str = "FastAPI Clean Architecture"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # Database settings (SQLite for now due to Python 3.13 compatibility issues)
    database_url: str = "sqlite:///./backend.db"
    async_database_url: str = "sqlite+aiosqlite:///./backend.db"
    
    # Redis settings
    redis_url: str = "redis://localhost:6379"
    
    # JWT settings
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    class Config:
        env_file = ".env"


settings = Settings()