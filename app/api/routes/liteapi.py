"""
LiteAPI Hotels Route
--------------------
Exposes live hotel search + rates from LiteAPI as a FastAPI endpoint.
Kept separate from the Amadeus-based hotel search intentionally —
this is purely for the hotel display tab, not the booking flow.

Endpoint:
    GET /api/hotels/liteapi?city_name=Boston&country_code=US&checkin=2026-07-01&checkout=2026-07-02&adults=2&limit=5
"""

from fastapi import APIRouter, HTTPException, Query
import os
from app.services.liteapi_service import search_hotels, get_hotel_rates, HotelSummary, RoomOffer

router = APIRouter()


@router.get("/liteapi")
async def get_liteapi_hotels(
    city_name:    str = Query("Boston",     description="City to search"),
    country_code: str = Query("US",         description="Two-letter country code"),
    checkin:      str = Query("2026-07-01", description="Check-in date YYYY-MM-DD"),
    checkout:     str = Query("2026-07-02", description="Check-out date YYYY-MM-DD"),
    adults:       int = Query(2,            description="Number of adults"),
    limit:        int = Query(5,            description="Max number of hotels"),
):
    """
    Search hotels via LiteAPI and return display-ready data including room rates.
    Used by the Hotel Explorer tab in the frontend.
    """
    if not os.getenv("CONNECT_API_KEY", ""):
        raise HTTPException(
            status_code=503,
            detail="CONNECT_API_KEY not configured. Add it to your .env file."
        )

    try:
        # Step 1 — search hotels by city
        hotels: list[HotelSummary] = search_hotels(
            city_name    = city_name,
            country_code = country_code,
            limit        = limit,
        )
        if not hotels:
            raise HTTPException(status_code=404, detail=f"No hotels found in {city_name}")

        # Step 2 — fetch rates for all returned hotel IDs
        hotel_ids = [h.hotel_id for h in hotels]
        offers: list[RoomOffer] = get_hotel_rates(
            hotel_ids = hotel_ids,
            checkin   = checkin,
            checkout  = checkout,
            adults    = adults,
        )

        # Step 3 — distribute offers across hotels
        # In production LiteAPI returns hotelId per offer for exact mapping
        offers_per_hotel = max(1, len(offers) // max(len(hotels), 1))

        result = []
        for i, hotel in enumerate(hotels):
            hotel_offers = offers[i * offers_per_hotel : (i + 1) * offers_per_hotel + 1]
            result.append({
                "hotel_id":    hotel.hotel_id,
                "name":        hotel.name,
                "city":        hotel.city,
                "country":     hotel.country,
                "address":     hotel.address,
                "stars":       hotel.stars,
                "rating":      hotel.rating,
                "review_count":hotel.review_count,
                "thumbnail":   hotel.thumbnail,
                "description": hotel.description,
                "chain":       hotel.chain,
                "lowest_rate": min((o.price for o in hotel_offers), default=None),
                "offers": [
                    {
                        "room_name":     o.room_name,
                        "board_type":    o.board_type,
                        "price":         o.price,
                        "currency":      o.currency,
                        "tax_amount":    o.tax_amount,
                        "total":         round(o.price + o.tax_amount, 2),
                        "refundable":    o.refundable,
                        "cancel_time":   o.cancel_time,
                        "max_occupancy": o.max_occupancy,
                    }
                    for o in hotel_offers
                ],
            })

        return {
            "city":        city_name,
            "country":     country_code,
            "checkin":     checkin,
            "checkout":    checkout,
            "adults":      adults,
            "hotel_count": len(result),
            "hotels":      result,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LiteAPI error: {str(e)}")