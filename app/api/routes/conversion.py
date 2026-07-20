from fastapi import APIRouter, HTTPException
from app.services.conversion_engine import conversion_engine
from app.services.rewardscc_service import rewards_cc_service
from app.models.schemas import ConversionRequest, ConversionResult
from typing import List

router = APIRouter()

@router.get("/{card_key}/partners")
async def get_transfer_partners(card_key: str):
    """Get all hotel transfer partners and ratios for a card (Edge Case #3)."""
    partners = await rewards_cc_service.get_transfer_partners(card_key)
    if not partners:
        raise HTTPException(status_code=404, detail=f"No partners found for {card_key}")
    return {
        "card_key": card_key,
        "hotel_transfer_partners": [p.model_dump() for p in partners],
    }

@router.post("/convert", response_model=ConversionResult)
async def convert_points(request: ConversionRequest, user_id: str):
    """
    Convert card points to hotel loyalty points.
    Validates denomination and fetches live ratio.
    """
    return await conversion_engine.convert_points(request, user_id)