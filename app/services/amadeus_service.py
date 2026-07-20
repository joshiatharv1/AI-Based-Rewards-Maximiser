"""
Amadeus Hotel Service
---------------------
Searches hotels via Amadeus sandbox API.
Sandbox docs: https://developers.amadeus.com/self-service/category/hotels

Steps to get credentials (free):
1. Go to https://developers.amadeus.com
2. Sign up (no card required)
3. Create an app → get Client ID + Client Secret
4. Add to .env file

Falls back to mock data if credentials not set.
"""

import httpx
from typing import Optional
from app.core.config import settings
from app.models.schemas import HotelOffer, HotelSearchRequest

# ─── Mock Hotel Data ───────────────────────────────────────────────────────────
MOCK_HOTELS = [
    {
        "hotel_id": "MCNYC001",
        "hotel_name": "Marriott Marquis Times Square",
        "chain_code": "MC",
        "loyalty_program": "Marriott Bonvoy",
        "room_rate_per_night": 289.00,
        "currency": "USD",
    },
    {
        "hotel_id": "HHNYC001",
        "hotel_name": "Hilton Midtown New York",
        "chain_code": "HH",
        "loyalty_program": "Hilton Honors",
        "room_rate_per_night": 245.00,
        "currency": "USD",
    },
    {
        "hotel_id": "HYNYC001",
        "hotel_name": "Park Hyatt New York",
        "chain_code": "HY",
        "loyalty_program": "World of Hyatt",
        "room_rate_per_night": 425.00,
        "currency": "USD",
    },
    {
        "hotel_id": "IHNYC001",
        "hotel_name": "InterContinental New York Times Square",
        "chain_code": "IC",
        "loyalty_program": "IHG One Rewards",
        "room_rate_per_night": 310.00,
        "currency": "USD",
    },
]

TAX_RATE = 0.14          # 14% NYC hotel tax
RESORT_FEE_FLAT = 35.00  # flat resort fee per stay


class AmadeusService:
    def __init__(self):
        self.client_id     = settings.AMADEUS_CLIENT_ID
        self.client_secret = settings.AMADEUS_CLIENT_SECRET
        self.base_url      = settings.AMADEUS_BASE_URL
        self.use_mock      = (self.client_id == "YOUR_AMADEUS_CLIENT_ID_HERE")
        self._token: Optional[str] = None

    async def _get_token(self) -> str:
        """OAuth2 client credentials flow for Amadeus."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/security/oauth2/token",
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            self._token = response.json()["access_token"]
            return self._token

    async def search_hotels(self, request: HotelSearchRequest) -> list[HotelOffer]:
        """Search available hotels for given dates and city."""
        if self.use_mock:
            return self._mock_hotel_search(request)

        try:
            token = await self._get_token()
            async with httpx.AsyncClient() as client:
                # Step 1: Get hotel IDs for city
                hotel_list_response = await client.get(
                    f"{self.base_url}/v1/reference-data/locations/hotels/by-city",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "cityCode": request.city_code,
                        "radius": 5,
                        "radiusUnit": "KM",
                        "hotelSource": "ALL",
                    },
                )
                hotel_list_response.raise_for_status()
                hotel_ids = [
                    h["hotelId"]
                    for h in hotel_list_response.json().get("data", [])[:10]
                ]

                # Step 2: Get offers for those hotels
                offers_response = await client.get(
                    f"{self.base_url}/v3/shopping/hotel-offers",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "hotelIds":  ",".join(hotel_ids),
                        "checkInDate":  request.check_in,
                        "checkOutDate": request.check_out,
                        "adults":       request.adults,
                        "currency":     "USD",
                    },
                )
                offers_response.raise_for_status()
                return self._parse_offers(offers_response.json(), request)

        except Exception as e:
            print(f"Amadeus API error: {e} — falling back to mock data")
            return self._mock_hotel_search(request)

    def _mock_hotel_search(self, request: HotelSearchRequest) -> list[HotelOffer]:
        """Generate mock hotel offers with full pricing."""
        from datetime import datetime
        nights = max(1, (
            datetime.fromisoformat(request.check_out) -
            datetime.fromisoformat(request.check_in)
        ).days)

        offers = []
        for h in MOCK_HOTELS:
            subtotal    = h["room_rate_per_night"] * nights
            taxes       = round(subtotal * TAX_RATE, 2)
            resort_fees = RESORT_FEE_FLAT
            total       = round(subtotal + taxes + resort_fees, 2)

            offers.append(HotelOffer(
                hotel_id             = h["hotel_id"],
                hotel_name           = h["hotel_name"],
                chain_code           = h["chain_code"],
                loyalty_program      = h["loyalty_program"],
                room_rate_per_night  = h["room_rate_per_night"],
                total_nights         = nights,
                room_subtotal        = round(subtotal, 2),
                taxes                = taxes,
                resort_fees          = resort_fees,
                total_price          = total,
                currency             = h["currency"],
            ))
        return offers

    def _parse_offers(self, data: dict, request: HotelSearchRequest) -> list[HotelOffer]:
        """Parse real Amadeus API response into HotelOffer models."""
        from datetime import datetime
        nights = max(1, (
            datetime.fromisoformat(request.check_out) -
            datetime.fromisoformat(request.check_in)
        ).days)

        offers = []
        for item in data.get("data", []):
            hotel  = item.get("hotel", {})
            offer  = item.get("offers", [{}])[0]
            price  = offer.get("price", {})
            total  = float(price.get("total", 0))
            base   = float(price.get("base", total * 0.86))
            taxes  = total - base

            # Map chain code to loyalty program
            chain_code = hotel.get("chainCode", "XX")
            loyalty_map = {
                "MC": "Marriott Bonvoy",
                "HH": "Hilton Honors",
                "HY": "World of Hyatt",
                "IC": "IHG One Rewards",
                "WY": "Wyndham Rewards",
            }

            offers.append(HotelOffer(
                hotel_id            = hotel.get("hotelId", ""),
                hotel_name          = hotel.get("name", "Unknown Hotel"),
                chain_code          = chain_code,
                loyalty_program     = loyalty_map.get(chain_code, "Hotel Loyalty Program"),
                room_rate_per_night = round(base / nights, 2),
                total_nights        = nights,
                room_subtotal       = round(base, 2),
                taxes               = round(taxes, 2),
                resort_fees         = 0.0,
                total_price         = round(total, 2),
                currency            = price.get("currency", "USD"),
            ))
        return offers


amadeus_service = AmadeusService()