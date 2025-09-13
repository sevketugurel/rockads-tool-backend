from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    app_name: str = "FastAPI Video Localization"
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

    # Google Gemini API settings
    gemini_api_key: str = "your-gemini-api-key"
    gemini_model: str = "gemini-1.5-flash"  # Changed from 2.5-pro to 1.5-flash for better quota availability
    gemini_timeout: int = 300  # 5 minutes timeout for processing

    # File upload settings
    upload_dir: str = "uploads"
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    allowed_video_types: list = ["video/mp4", "video/avi", "video/mov", "video/mkv", "video/wmv"]

    # Video processing settings
    temp_dir: str = "temp"
    output_dir: str = "output"

    # ElevenLabs settings (for future use)
    elevenlabs_api_key: str = "your-elevenlabs-api-key"
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"  # Adam voice - ElevenLabs default

    class Config:
        env_file = ".env"


settings = Settings()