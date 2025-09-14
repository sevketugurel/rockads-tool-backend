import json
import os
import logging
from typing import List, Dict, Any, Optional

import google.generativeai as genai

from core.config.settings import settings
from domain.entities.video import Video
from domain.entities.country import Country
from application.services.ai.cultural_analysis_service import CulturalAnalysisService

from domain.repositories.video_repository import VideoRepository
from domain.repositories.transcription_repository import TranscriptionRepository
from domain.repositories.translation_repository import TranslationRepository
from domain.repositories.country_repository import CountryRepository

logger = logging.getLogger(__name__)


class CampaignGenerationService:
    """Generate platform-specific campaign plans per country using Gemini + lightweight RAG."""

    def __init__(
        self,
        video_repo: VideoRepository,
        transcription_repo: TranscriptionRepository,
        translation_repo: TranslationRepository,
        country_repo: CountryRepository,
    ):
        if not settings.gemini_api_key or settings.gemini_api_key == "your-gemini-api-key":
            raise ValueError("Gemini API key not configured. Please set GEMINI_API_KEY in your .env file")

        genai.configure(api_key=settings.gemini_api_key, transport="rest")
        self.model = genai.GenerativeModel(settings.gemini_model)

        self.video_repo = video_repo
        self.transcription_repo = transcription_repo
        self.translation_repo = translation_repo
        self.country_repo = country_repo

        self.cultural = CulturalAnalysisService()
        self.kb_dir = os.path.join("data", "ad_playbooks")

    def _load_json(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.kb_dir, filename)
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {filename}: {e}")
        return {}

    async def _gather_texts(self, video_id: int) -> Dict[str, Any]:
        transcription = await self.transcription_repo.get_by_video_id(video_id)
        translations = await self.translation_repo.get_by_video_id(video_id)
        return {
            "transcription_text": getattr(transcription, "full_text", None),
            "translation_texts": [t.full_translated_text for t in translations if t.full_translated_text] if translations else [],
        }

    def _platform_files(self, platform: str) -> Dict[str, str]:
        platform = platform.lower()
        mapping = {
            "facebook": ("meta_playbook.json", "meta_policies.json"),
            "meta": ("meta_playbook.json", "meta_policies.json"),
            "google": ("google_playbook.json", "google_policies.json"),
            "tiktok": ("tiktok_playbook.json", "tiktok_policies.json"),
        }
        play, pol = mapping.get(platform, ("generic_playbook.json", "generic_policies.json"))
        return {"playbook": play, "policies": pol}

    def _build_platform_prompt(
        self,
        *,
        platform: str,
        analysis: Dict[str, Any],
        playbook: Dict[str, Any],
        policies: Dict[str, Any],
        objective: str,
        currency: str,
        country_code: str = "US",
    ) -> str:
        # Determine response language based on country
        language_instructions = {
            "TR": "IMPORTANT: Respond in Turkish language. All campaign content (adText, call_to_action, targeting demographics, policy_notes, hashtags, etc.) must be in Turkish. Use Turkish alphabet and Turkish cultural context.",
            "DE": "IMPORTANT: Respond in German language. All campaign content must be in German. Use German alphabet and German cultural context.",
            "ES": "IMPORTANT: Respond in Spanish language. All campaign content must be in Spanish. Use Spanish alphabet and Spanish cultural context.",
            "FR": "IMPORTANT: Respond in French language. All campaign content must be in French. Use French alphabet and French cultural context.",
            "IT": "IMPORTANT: Respond in Italian language. All campaign content must be in Italian. Use Italian alphabet and Italian cultural context.",
            "CN": "IMPORTANT: Respond in Chinese language (Simplified Chinese). All campaign content must be in Chinese. Use Chinese characters and Chinese cultural context.",
            "KP": "IMPORTANT: Respond in Korean language. All campaign content must be in Korean. Use Korean alphabet (Hangul) and Korean cultural context.",
            "US": "IMPORTANT: Respond in English language. All campaign content must be in English. Use American English and American cultural context.",
            "GB": "IMPORTANT: Respond in English language. All campaign content must be in English. Use British English and British cultural context.",
            "CA": "IMPORTANT: Respond in English or French language (based on region). All campaign content must be in the appropriate language. Use Canadian cultural context.",
            "AU": "IMPORTANT: Respond in English language. All campaign content must be in English. Use Australian English and Australian cultural context.",
            "JP": "IMPORTANT: Respond in Japanese language. All campaign content must be in Japanese. Use Japanese characters (Hiragana, Katakana, Kanji) and Japanese cultural context.",
            "RU": "IMPORTANT: Respond in Russian language. All campaign content must be in Russian. Use Cyrillic alphabet and Russian cultural context.",
            "BR": "IMPORTANT: Respond in Portuguese language. All campaign content must be in Brazilian Portuguese. Use Portuguese alphabet and Brazilian cultural context.",
            "MX": "IMPORTANT: Respond in Spanish language. All campaign content must be in Mexican Spanish. Use Spanish alphabet and Mexican cultural context.",
            "IN": "IMPORTANT: Respond in English language with Indian context. All campaign content must be in English but adapted for Indian market and cultural context.",
            "AR": "IMPORTANT: Respond in Spanish language. All campaign content must be in Argentinian Spanish. Use Spanish alphabet and Argentinian cultural context.",
        }
        
        language_instruction = language_instructions.get(country_code, "IMPORTANT: Respond in English language. All campaign content must be in English.")
        
        return f"""
You are an expert {platform} ads strategist.
Create a localized campaign plan using the inputs below. Output STRICT JSON only, no extra text.

{language_instruction}

OBJECTIVE: {objective}

COUNTRY STRATEGY (analysis):
{json.dumps(analysis, indent=2)}

PLATFORM PLAYBOOK:
{json.dumps(playbook, indent=2)}

POLICIES (be compliant):
{json.dumps(policies, indent=2)}

SCHEMA:
{{
  "campaign": {{
    "platform": "{platform}",
    "adText": "...",
    "targeting": {{"ageRange": "..", "interests": [".."], "demographics": ".."}},
    "budget": {{"suggested": 0, "currency": "{currency}"}},
    "call_to_action": "...",
    "creative": {{"aspect_ratio": "..", "headline": "..", "hashtags": [".."]}},
    "policy_notes": [".."],
    "measurement": {{"utm": "...", "experiments": ["A/B headline", "Creative ratio"]}}
  }},
  "variants": [
    {{"adText": "...", "headline": "..."}}
  ]
}}
"""

    async def generate(
        self,
        *,
        video_id: int,
        country_codes: List[str],
        platforms: Optional[List[str]] = None,
        objective: str = "conversions",
        max_variants: int = 2,
    ) -> Dict[str, Any]:
        platforms = platforms or ["facebook", "google", "tiktok"]

        video: Optional[Video] = await self.video_repo.get_by_id(video_id)
        if not video:
            raise ValueError("Video not found")

        texts = await self._gather_texts(video_id)

        campaigns: List[Dict[str, Any]] = []
        for code in country_codes:
            country: Optional[Country] = await self.country_repo.get_by_country_code(code)
            if not country:
                campaigns.append({"country_code": code, "error": "Country not found"})
                continue

            # Cultural analysis (includes product inference + web research inside)
            analysis = await self.cultural.analyze_for_country(
                video=video,
                country=country,
                video_context={"duration": video.duration, "language": video.language, "filename": video.original_filename},
                transcription_text=texts.get("transcription_text"),
                translation_texts=texts.get("translation_texts"),
            )

            currency = country.currency or ("USD" if country.country_code == "US" else "EUR")

            for platform in platforms:
                files = self._platform_files(platform)
                playbook = self._load_json(files["playbook"]) or {"best_practices": []}
                policies = self._load_json(files["policies"]) or {"dos": [], "donts": []}

                prompt = self._build_platform_prompt(
                    platform=platform,
                    analysis=analysis,
                    playbook=playbook,
                    policies=policies,
                    objective=objective,
                    currency=currency,
                    country_code=country.country_code,
                )

                try:
                    resp = self.model.generate_content(prompt)
                    txt = (resp.text or "{}").strip()
                    if txt and txt[0] != '{':
                        s, e = txt.find('{'), txt.rfind('}')
                        txt = txt[s:e+1] if s != -1 and e != -1 else '{}'
                    parsed = json.loads(txt)
                except Exception as e:
                    logger.warning(f"Gemini campaign generation failed ({platform}, {code}): {e}")
                    # Safe fallback from analysis
                    parsed = {
                        "campaign": {
                            "platform": platform,
                            "adText": (analysis.get("adaptations") or ["Localized ad copy"])[0],
                            "targeting": {
                                "ageRange": "25-45",
                                "interests": analysis.get("target_audience", {}).get("interests", ["technology"]),
                                "demographics": ", ".join(analysis.get("target_audience", {}).get("demographics", ["tech-savvy"])) or "",
                            },
                            "budget": {"suggested": max(500, int((analysis.get("scores", {}).get("market_potential_percent", 60) or 60) * 20)), "currency": currency},
                            "call_to_action": "Learn More",
                            "creative": {"aspect_ratio": "1:1", "headline": (analysis.get("strengths") or [""])[0], "hashtags": ["#ad"]},
                            "policy_notes": [],
                            "measurement": {"utm": "utm_source=ai&utm_medium=ad", "experiments": ["A/B headline"]},
                        },
                        "variants": [],
                    }

                # Constrain variant count
                if parsed.get("variants") and isinstance(parsed["variants"], list):
                    parsed["variants"] = parsed["variants"][:max_variants]

                campaigns.append({
                    "country_code": country.country_code,
                    "country_name": country.country_name,
                    "platform": platform,
                    **parsed,
                })

        return {"video_id": video_id, "campaigns": campaigns}

