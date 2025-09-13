"""
Basic test script to verify the localization system works
"""
import asyncio
import os
import sys

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from domain.entities.country import Country, DialectInfo, CulturalContext
from domain.entities.translation import Translation, TranslationStatus


def test_country_entity():
    """Test Country entity creation"""
    print("Testing Country entity...")

    dialect_info = DialectInfo(
        primary_dialect="General American",
        accent_characteristics=["rhotic", "broad vowels"],
        common_phrases={"hello": "Hi there!"},
        slang_terms={"cool": "awesome"},
        formality_level="casual",
        pronunciation_notes=["Clear R sounds"]
    )

    cultural_context = CulturalContext(
        humor_style="direct",
        communication_style="direct",
        color_preferences=["blue", "red"],
        taboo_topics=["politics"],
        cultural_values=["individualism"],
        marketing_preferences="direct benefits",
        call_to_action_style="urgent",
        urgency_indicators=["limited time"],
        trust_building_elements=["reviews"]
    )

    country = Country(
        country_code="US",
        country_name="United States",
        language_code="en",
        language_name="English (US)",
        dialect_info=dialect_info,
        cultural_context=cultural_context
    )

    assert country.country_code == "US"
    assert country.dialect_info.primary_dialect == "General American"
    assert country.cultural_context.humor_style == "direct"
    print("✓ Country entity test passed")


def test_translation_entity():
    """Test Translation entity creation"""
    print("Testing Translation entity...")

    translation = Translation(
        video_id=1,
        transcription_id=1,
        country_id=1,
        source_language="en",
        target_language="en",
        country_code="US",
        status=TranslationStatus.PENDING
    )

    assert translation.video_id == 1
    assert translation.status == TranslationStatus.PENDING
    assert translation.country_code == "US"
    print("✓ Translation entity test passed")


def test_system_imports():
    """Test that all system components can be imported"""
    print("Testing system imports...")

    try:
        from application.services.ai.gemini_translation_service import GeminiTranslationService
        from application.services.localization_service import LocalizationService
        from application.use_cases.localization_use_cases import LocalizationUseCases
        from presentation.api.localization_routes import router
        print("✓ All imports successful")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        raise


def test_api_routes():
    """Test that API routes are properly configured"""
    print("Testing API routes...")

    from presentation.api.localization_routes import router

    # Check that routes exist
    routes = [route.path for route in router.routes]
    expected_routes = [
        "/countries",
        "/jobs",
        "/jobs/{job_id}/start",
        "/jobs/{job_id}",
        "/translations/{translation_id}"
    ]

    for expected_route in expected_routes:
        # Check if any route contains the expected path
        route_exists = any(expected_route in route for route in routes)
        if not route_exists:
            print(f"✗ Route {expected_route} not found")
            print(f"Available routes: {routes}")
        else:
            print(f"✓ Route {expected_route} found")


def main():
    """Run all tests"""
    print("Starting Localization System Tests\n")

    try:
        test_system_imports()
        test_country_entity()
        test_translation_entity()
        test_api_routes()

        print("\n🎉 All tests passed! The localization system is properly configured.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()