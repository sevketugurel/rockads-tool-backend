import json
import logging
import os
from typing import List, Dict, Any, Optional

import google.generativeai as genai

from core.config.settings import settings
from domain.entities.country import Country
from domain.entities.video import Video

logger = logging.getLogger(__name__)


class CulturalAnalysisService:
    """Gemini-powered cultural analysis with lightweight local RAG.

    - Loads country-specific cultural snippets from a local knowledge base (JSON/MD).
    - Retrieves relevant entries per country and feeds them into Gemini with video context.
    - Produces structured insights: strengths, risks, adaptations, examples, compliance notes.
    """

    def __init__(self):
        if not settings.gemini_api_key or settings.gemini_api_key == "your-gemini-api-key":
            raise ValueError("Gemini API key not configured. Please set GEMINI_API_KEY in your .env file")
        genai.configure(api_key=settings.gemini_api_key, transport="rest")
        self.model = genai.GenerativeModel(settings.gemini_model)

        # Knowledge base path
        self.kb_dir = getattr(settings, "knowledge_base_dir", "data/cultural_knowledge")
        self.kb_path_json = os.path.join(self.kb_dir, "country_insights.json")
        self._kb = None

    def _load_kb(self) -> List[Dict[str, Any]]:
        if self._kb is not None:
            return self._kb
        try:
            if os.path.exists(self.kb_path_json):
                with open(self.kb_path_json, "r", encoding="utf-8") as f:
                    self._kb = json.load(f)
            else:
                self._kb = []
        except Exception as e:
            logger.warning(f"Failed to load knowledge base: {e}")
            self._kb = []
        return self._kb

    def _retrieve_country_context(self, country_code: str, max_items: int = 6) -> List[Dict[str, Any]]:
        """Very lightweight retrieval: filter by country_code and select top priority items."""
        kb = self._load_kb()
        items = [d for d in kb if d.get("country_code") == country_code.upper()]
        # Sort by priority desc, then recency if provided
        items.sort(key=lambda x: (x.get("priority", 0), x.get("year", 0)), reverse=True)
        return items[:max_items]

    def _build_prompt(self, video: Video, country: Country, video_context: Dict[str, Any], kb_items: List[Dict[str, Any]]) -> str:
        return f"""
You are a senior cultural strategist and advertising effectiveness expert.
Analyze the following advertisement and provide cultural insights for {country.country_name}.
Return STRICT JSON only with the schema below.

VIDEO CONTEXT (auto-extracted):
{json.dumps(video_context or {}, indent=2)}

AD METADATA:
- Original filename: {video.original_filename}
- Duration: {video.duration}
- Language: {video.language}

COUNTRY PROFILE (database):
- Language: {country.language_name} ({country.language_code})
- Dialect: {country.dialect_info.primary_dialect}
- Communication style: {country.cultural_context.communication_style}
- Marketing preferences: {country.cultural_context.marketing_preferences}
- Cultural values: {country.cultural_context.cultural_values}
- Taboo topics: {country.cultural_context.taboo_topics}

KNOWLEDGE BASE SNIPPETS (RAG):
{json.dumps(kb_items, indent=2)}

TASK:
1) Strengths: What will likely resonate culturally and commercially? (5 bullets max)
2) Risks: Cultural pitfalls, sensitivities, or misinterpretations to avoid (5 bullets max)
3) Adaptations: Concrete, actionable changes for this market (copy, visuals, pacing, CTA)
4) Messaging & CTA: 2 localized CTA examples aligned with local tone (short)
5) Compliance & Brand Safety: brief checklist
6) KPI hypotheses: expected impact areas and how to measure (brief)

STRICT JSON SCHEMA (no extra text):
{{
  "country_code": "{country.country_code}",
  "strengths": ["..."],
  "risks": ["..."],
  "adaptations": ["..."],
  "messaging": {{ "cta_examples": ["...", "..."] }},
  "compliance": ["..."],
  "kpi_hypotheses": ["..."]
}}
"""

    async def analyze_for_country(self, *, video: Video, country: Country, video_context: Dict[str, Any]) -> Dict[str, Any]:
        """Run Gemini with RAG snippets and return structured cultural analysis."""
        kb_items = self._retrieve_country_context(country.country_code)
        prompt = self._build_prompt(video, country, video_context, kb_items)
        try:
            resp = self.model.generate_content(prompt)
            text = (resp.text or "").strip()
            # Ensure we only have JSON
            if text and text[0] != '{':
                # Try extracting JSON block
                start = text.find('{')
                end = text.rfind('}')
                text = text[start:end+1] if start != -1 and end != -1 else '{}'
            return json.loads(text)
        except Exception as e:
            logger.error(f"Cultural analysis failed: {e}")
            return {
                "country_code": country.country_code,
                "error": str(e)
            }

