"""
LiteAPI Hotel Data Fetcher
--------------------------
Standalone module for fetching hotel search and rate data from LiteAPI.
Kept separate from the main Optivoy rewards engine intentionally —
this module is purely for hotel data display and does not touch
the points/booking logic.

Docs: https://docs.liteapi.travel
Free sandbox key available at: https://liteapi.travel

Usage:
    python liteapi_hotels.py

Environment variable required in .env:
    CONNECT_API_KEY=your_liteapi_key
"""

import os
import requests
from dataclasses import dataclass, field
from typing import Optional
import json
from dotenv import load_dotenv

load_dotenv()  # works both standalone and inside FastAPI

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_URL = "https://api.liteapi.travel/v3.0"

def _get_headers():
    """Read API key fresh each call so .env changes are picked up."""
    api_key = os.getenv("CONNECT_API_KEY", "")
    return {
        "X-API-Key":    api_key,
        "accept":       "application/json",
        "Content-Type": "application/json",
    }

# ─── Data models ──────────────────────────────────────────────────────────────

@dataclass
class HotelSummary:
    """Clean, display-ready hotel object extracted from LiteAPI response."""
    hotel_id:     str
    name:         str
    city:         str
    country:      str
    address:      str
    stars:        int
    rating:       float
    review_count: int
    thumbnail:    str
    description:  str
    latitude:     float
    longitude:    float
    chain:        str = "Independent"

@dataclass
class RoomOffer:
    """A single bookable room offer."""
    offer_id:       str
    room_name:      str
    board_type:     str          # e.g. "Room Only", "Breakfast Included"
    price:          float
    currency:       str
    tax_amount:     float
    refundable:     bool
    cancel_time:    Optional[str] = None
    max_occupancy:  int = 2

@dataclass
class HotelWithRates:
    """Hotel + its available room offers for a given date range."""
    hotel:  HotelSummary
    offers: list[RoomOffer] = field(default_factory=list)

    @property
    def lowest_rate(self) -> Optional[float]:
        if not self.offers:
            return None
        return min(o.price for o in self.offers)

    @property
    def lowest_rate_room(self) -> Optional[RoomOffer]:
        if not self.offers:
            return None
        return min(self.offers, key=lambda o: o.price)


# ─── API functions ─────────────────────────────────────────────────────────────

def search_hotels(
    city_name:    str  = "Boston",
    country_code: str  = "US",
    limit:        int  = 5,
) -> list[HotelSummary]:
    """
    Search hotels by city.
    Endpoint: GET /v3.0/data/hotels
    Returns a list of HotelSummary objects with only display-relevant fields.
    """
    if not os.getenv("CONNECT_API_KEY", ""):
        raise ValueError("CONNECT_API_KEY not set in .env file.")

    url = f"{BASE_URL}/data/hotels"
    params = {
        "countryCode": country_code,
        "cityName":    city_name,
        "limit":       limit,
    }

    try:
        res = requests.get(url, headers=_get_headers(), params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
    except requests.exceptions.HTTPError as e:
        print(f"[LiteAPI] Hotel search failed: {e} — {res.text[:300]}")
        return []
    except Exception as e:
        print(f"[LiteAPI] Request error: {e}")
        return []

    hotels = []
    for h in data.get("data", []):
        # Strip HTML tags from description for clean display
        desc = h.get("hotelDescription", "")
        desc = _strip_html(desc)[:200] + "..." if len(desc) > 200 else _strip_html(desc)

        hotels.append(HotelSummary(
            hotel_id    = h.get("id", ""),
            name        = h.get("name", "Unknown Hotel"),
            city        = h.get("city", city_name),
            country     = h.get("country", country_code).upper(),
            address     = h.get("address", ""),
            stars       = int(h.get("stars", 0)),
            rating      = float(h.get("rating", 0)),
            review_count= int(h.get("reviewCount", 0)),
            thumbnail   = h.get("thumbnail", ""),
            description = desc,
            latitude    = float(h.get("latitude", 0)),
            longitude   = float(h.get("longitude", 0)),
            chain       = h.get("chain", "Independent") or "Independent",
        ))

    print(f"[LiteAPI] Found {len(hotels)} hotels in {city_name}")
    return hotels


def get_hotel_rates(
    hotel_ids:        list[str],
    checkin:          str,
    checkout:         str,
    adults:           int  = 2,
    currency:         str  = "USD",
    guest_nationality:str  = "US",
) -> list[RoomOffer]:
    """
    Fetch available room rates for given hotel IDs and dates.
    Endpoint: POST /v3.0/hotels/rates
    Returns a flat list of RoomOffer objects sorted by price.
    """
    if not os.getenv("CONNECT_API_KEY", ""):
        raise ValueError("CONNECT_API_KEY not set in .env file.")

    url = f"{BASE_URL}/hotels/rates"
    payload = {
        "currency":         currency,
        "guestNationality": guest_nationality,
        "checkin":          checkin,
        "checkout":         checkout,
        "occupancies":      [{"adults": adults}],
        "hotelIds":         hotel_ids,
    }

    try:
        res = requests.post(url, headers=_get_headers(), json=payload, timeout=20)
        res.raise_for_status()
        data = res.json()
    except requests.exceptions.HTTPError as e:
        print(f"[LiteAPI] Rates fetch failed: {e} — {res.text[:300]}")
        return []
    except Exception as e:
        print(f"[LiteAPI] Request error: {e}")
        return []

    offers = []
    for hotel_data in data.get("data", []):
        for offer in hotel_data.get("offers", []):
            rates = offer.get("rates", [{}])
            rate  = rates[0] if rates else {}

            retail    = rate.get("retailRate", {})
            tax_list  = retail.get("taxesAndFees", [])
            tax_amt   = sum(t.get("amount", 0) for t in tax_list)

            cancel    = rate.get("cancellationPolicies", {})
            refundable= cancel.get("refundableTag", "") == "RFN"
            cancel_infos = cancel.get("cancelPolicyInfos", [])
            cancel_time  = cancel_infos[0].get("cancelTime") if cancel_infos else None

            price = float(offer.get("offerRetailRate", {}).get("amount", 0))
            if price == 0:
                continue  # Skip offers with no price

            offers.append(RoomOffer(
                offer_id      = offer.get("offerId", ""),
                room_name     = rate.get("name", "Standard Room"),
                board_type    = rate.get("boardName", "Room Only"),
                price         = price,
                currency      = offer.get("offerRetailRate", {}).get("currency", currency),
                tax_amount    = tax_amt,
                refundable    = refundable,
                cancel_time   = cancel_time,
                max_occupancy = rate.get("maxOccupancy", 2),
            ))

    # Sort by price ascending
    offers.sort(key=lambda o: o.price)
    print(f"[LiteAPI] Found {len(offers)} room offers")
    return offers


def get_hotels_with_rates(
    city_name:    str,
    country_code: str,
    checkin:      str,
    checkout:     str,
    adults:       int = 2,
    limit:        int = 5,
) -> list[HotelWithRates]:
    """
    Combined call: search hotels then fetch rates for each.
    Returns HotelWithRates objects ready for display.
    """
    hotels = search_hotels(city_name, country_code, limit)
    if not hotels:
        return []

    hotel_ids = [h.hotel_id for h in hotels]
    all_offers = get_hotel_rates(hotel_ids, checkin, checkout, adults)

    # In practice LiteAPI returns offers per hotel — for display purposes
    # we attach all offers to the first hotel as a demo
    # In production you'd map by hotelId in the rates response
    results = []
    for hotel in hotels:
        results.append(HotelWithRates(hotel=hotel, offers=all_offers[:3]))

    return results


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Remove HTML tags for clean text display."""
    import re
    return re.sub(r"<[^>]+>", " ", text).strip()


def export_to_json(hotels: list[HotelWithRates], path: str = "hotel_data.json"):
    """Export fetched data to JSON for the React frontend to consume."""
    output = []
    for hw in hotels:
        h = hw.hotel
        output.append({
            "hotel_id":    h.hotel_id,
            "name":        h.name,
            "city":        h.city,
            "country":     h.country,
            "address":     h.address,
            "stars":       h.stars,
            "rating":      h.rating,
            "review_count":h.review_count,
            "thumbnail":   h.thumbnail,
            "description": h.description,
            "chain":       h.chain,
            "lowest_rate": hw.lowest_rate,
            "offers": [
                {
                    "room_name":  o.room_name,
                    "board_type": o.board_type,
                    "price":      o.price,
                    "currency":   o.currency,
                    "tax_amount": o.tax_amount,
                    "refundable": o.refundable,
                    "cancel_time":o.cancel_time,
                }
                for o in hw.offers
            ]
        })

    with open(path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"[LiteAPI] Exported {len(output)} hotels to {path}")


# ─── Entry point ──────────────────────────────────────────────────────────────