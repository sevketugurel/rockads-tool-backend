from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.database.connection import get_async_db

from infrastructure.database.video_repository_impl import VideoRepositoryImpl
from infrastructure.database.transcription_repository_impl import TranscriptionRepositoryImpl
from infrastructure.database.translation_repository_impl import TranslationRepositoryImpl
from infrastructure.database.country_repository_impl import CountryRepositoryImpl

from application.services.ai.campaign_generation_service import CampaignGenerationService

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignGenerateRequest(BaseModel):
    video_id: int = Field(..., description="Video ID")
    country_codes: List[str] = Field(..., description="Target country codes")
    platforms: Optional[List[str]] = Field(None, description="Platforms e.g., ['facebook','google','tiktok']")
    objective: str = Field("conversions", description="Campaign objective")
    max_variants: int = Field(2, ge=1, le=5)


@router.post("/generate")
async def generate_campaigns(req: CampaignGenerateRequest, session: AsyncSession = Depends(get_async_db)):
    """Generate platform-specific campaign plans per country using Gemini + RAG playbooks/policies."""
    try:
        service = CampaignGenerationService(
            video_repo=VideoRepositoryImpl(session),
            transcription_repo=TranscriptionRepositoryImpl(session),
            translation_repo=TranslationRepositoryImpl(session),
            country_repo=CountryRepositoryImpl(session),
        )
        result = await service.generate(
            video_id=req.video_id,
            country_codes=req.country_codes,
            platforms=req.platforms,
            objective=req.objective,
            max_variants=req.max_variants,
        )
        # Provide a compact projection for simple frontends
        compact: List[Dict[str, Any]] = []
        for c in result.get("campaigns", []):
            camp = c.get("campaign", {})
            compact.append({
                "country": c.get("country_code"),
                "platform": camp.get("platform"),
                "adText": camp.get("adText"),
                "targeting": camp.get("targeting", {}),
                "budget": camp.get("budget", {}),
            })
        return {"video_id": req.video_id, "campaigns": result.get("campaigns"), "compact": compact}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Campaign generation failed: {str(e)}")

