#!/usr/bin/env python3
"""
Test script to verify the video localization backend setup
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")

    try:
        # Test core imports
        from core.config.settings import settings
        print("✓ Core settings imported")

        # Test domain entities
        from domain.entities.video import Video, VideoStatus
        from domain.entities.transcription import Transcription, TranscriptionStatus
        print("✓ Domain entities imported")

        # Test repositories
        from domain.repositories.video_repository import VideoRepository
        from domain.repositories.transcription_repository import TranscriptionRepository
        print("✓ Repository interfaces imported")

        # Test implementations
        from infrastructure.database.video_repository_impl import VideoRepositoryImpl
        from infrastructure.database.transcription_repository_impl import TranscriptionRepositoryImpl
        print("✓ Repository implementations imported")

        # Test use cases
        from application.use_cases.video_use_cases import VideoUseCases
        print("✓ Use cases imported")

        # Test API routes
        from presentation.api.video_routes import router
        print("✓ API routes imported")

        # Test database models
        from infrastructure.database.models import VideoModel, TranscriptionModel
        print("✓ Database models imported")

        return True

    except Exception as e:
        print(f"✗ Import error: {str(e)}")
        return False

def test_configuration():
    """Test configuration settings"""
    print("\nTesting configuration...")

    try:
        from core.config.settings import settings

        print(f"App Name: {settings.app_name}")
        print(f"Database URL: {settings.database_url}")
        print(f"Upload Directory: {settings.upload_dir}")
        print(f"Max File Size: {settings.max_file_size} bytes")
        print(f"Allowed Video Types: {settings.allowed_video_types}")
        print(f"Gemini Model: {settings.gemini_model}")

        # Check if required directories exist
        upload_dir = Path(settings.upload_dir)
        temp_dir = Path(settings.temp_dir)
        output_dir = Path(settings.output_dir)

        print(f"Upload dir exists: {upload_dir.exists()}")
        print(f"Temp dir exists: {temp_dir.exists()}")
        print(f"Output dir exists: {output_dir.exists()}")

        # Check Gemini API key
        if settings.gemini_api_key == "your-gemini-api-key-here":
            print("⚠️  Warning: Gemini API key not configured")
        else:
            print("✓ Gemini API key configured")

        return True

    except Exception as e:
        print(f"✗ Configuration error: {str(e)}")
        return False

def test_database_connection():
    """Test database connection and models"""
    print("\nTesting database connection...")

    try:
        from infrastructure.database.connection import get_engine, get_async_db
        from infrastructure.database.models import Base, VideoModel, TranscriptionModel

        print("✓ Database modules imported successfully")
        print(f"✓ Models defined: {[cls.__tablename__ for cls in [VideoModel, TranscriptionModel]]}")

        return True

    except Exception as e:
        print(f"✗ Database connection error: {str(e)}")
        return False

async def main():
    """Main test function"""
    print("Video Localization Backend Setup Test")
    print("=" * 40)

    # Run tests
    import_success = await test_imports()
    config_success = test_configuration()
    db_success = test_database_connection()

    print("\n" + "=" * 40)
    print("Test Results:")
    print(f"Imports: {'✓ PASS' if import_success else '✗ FAIL'}")
    print(f"Configuration: {'✓ PASS' if config_success else '✗ FAIL'}")
    print(f"Database: {'✓ PASS' if db_success else '✗ FAIL'}")

    if all([import_success, config_success, db_success]):
        print("\n🎉 All tests passed! The backend is ready for testing.")
        print("\nNext steps:")
        print("1. Configure your Gemini API key in the .env file")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Start the server: python main.py")
        print("4. Test with Postman using the endpoints at http://localhost:8000/api/videos/")
    else:
        print("\n❌ Some tests failed. Please fix the issues before proceeding.")

    return all([import_success, config_success, db_success])

if __name__ == "__main__":
    asyncio.run(main())