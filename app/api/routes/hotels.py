from fastapi import APIRouter, HTTPException
from app.services.amadeus_service import amadeus_service
from app.models.schemas import HotelSearchRequest, HotelOffer
from typing import List

router = APIRouter()

@router.post("/search", response_model=List[HotelOffer])
async def search_hotels(request: HotelSearchRequest):
    """Search available hotels via Amadeus API."""
    hotels = await amadeus_service.search_hotels(request)
    if not hotels:
        raise HTTPException(status_code=404, detail="No hotels found for these dates.")
    return hotels