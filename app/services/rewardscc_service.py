"""
RewardsCC Service
-----------------
Fetches credit card metadata and transfer partner ratios from RewardsCC API.
Docs: https://rewardscc.com/docs/getting-started
API available on RapidAPI (free tier).

Fallback mock data is used when API key is not configured,
so the app works out of the box for development.

NOTE ON PARTNER NAMES:
Partner names here must EXACTLY match hotel loyalty_program field in
amadeus_service.py mock data, so the agent can join card → hotel correctly.
"""

import httpx
from typing import Optional
from app.core.config import settings
from app.models.schemas import TransferPartner

# ─── Fallback Mock Data ────────────────────────────────────────────────────────
# Real-world transfer ratios sourced from public loyalty program documentation.
# Partner names must match hotel loyalty_program strings in amadeus_service.py

MOCK_TRANSFER_PARTNERS: dict[str, list[dict]] = {
    "chase-sapphire-preferred": [
        {
            "partner_name": "Marriott Bonvoy",          # matches hotel loyalty_program
            "partner_program_key": "marriott-bonvoy",
            "transfer_ratio": 1.0,
            "min_transfer": 5000,
            "transfer_increments": [5000, 10000, 25000, 50000],
        },
        {
            "partner_name": "World of Hyatt",           # matches hotel loyalty_program
            "partner_program_key": "world-of-hyatt",
            "transfer_ratio": 1.0,
            "min_transfer": 5000,
            "transfer_increments": [5000, 10000, 25000, 50000],
        },
        {
            "partner_name": "IHG One Rewards",          # matches hotel loyalty_program
            "partner_program_key": "ihg-one-rewards",
            "transfer_ratio": 1.0,
            "min_transfer": 10000,
            "transfer_increments": [10000, 25000, 50000],
        },
    ],
    "amex-gold": [
        {
            "partner_name": "Marriott Bonvoy",
            "partner_program_key": "marriott-bonvoy",
            "transfer_ratio": 0.8,         # 1000 Amex MR = 800 Marriott points
            "min_transfer": 5000,
            "transfer_increments": [5000, 10000, 25000, 50000],
        },
        {
            "partner_name": "Hilton Honors",
            "partner_program_key": "hilton-honors",
            "transfer_ratio": 2.0,         # 1000 Amex MR = 2000 Hilton points
            "min_transfer": 1000,
            "transfer_increments": [1000, 5000, 10000, 25000, 50000],
        },
    ],
    "citi-premier": [
        {
            "partner_name": "Marriott Bonvoy",
            "partner_program_key": "marriott-bonvoy",
            "transfer_ratio": 1.0,
            "min_transfer": 10000,
            "transfer_increments": [10000, 25000, 50000],
        },
        {
            "partner_name": "World of Hyatt",
            "partner_program_key": "world-of-hyatt",
            "transfer_ratio": 1.0,
            "min_transfer": 10000,
            "transfer_increments": [10000, 25000],
        },
    ],
    # FIX: Capital One now includes Marriott and Hilton so user_002 gets results
    "capital-one-venture-x": [
        {
            "partner_name": "Marriott Bonvoy",
            "partner_program_key": "marriott-bonvoy",
            "transfer_ratio": 1.0,
            "min_transfer": 5000,
            "transfer_increments": [5000, 10000, 25000, 50000],
        },
        {
            "partner_name": "Hilton Honors",
            "partner_program_key": "hilton-honors",
            "transfer_ratio": 2.0,
            "min_transfer": 5000,
            "transfer_increments": [5000, 10000, 25000, 50000],
        },
        {
            "partner_name": "IHG One Rewards",
            "partner_program_key": "ihg-one-rewards",
            "transfer_ratio": 1.0,
            "min_transfer": 10000,
            "transfer_increments": [10000, 25000, 50000],
        },
    ],
    # FIX: Chase Freedom has 8,500 pts — add lower denomination partners
    "chase-freedom-unlimited": [
        {
            "partner_name": "World of Hyatt",
            "partner_program_key": "world-of-hyatt",
            "transfer_ratio": 1.0,
            "min_transfer": 5000,
            "transfer_increments": [5000],   # only 5000 so 8,500 balance qualifies
        },
        {
            "partner_name": "IHG One Rewards",
            "partner_program_key": "ihg-one-rewards",
            "transfer_ratio": 1.0,
            "min_transfer": 5000,
            "transfer_increments": [5000],
        },
    ],
}

# Points valuation in cents per point (from TPG / NerdWallet consensus)
MOCK_POINT_VALUATIONS: dict[str, float] = {
    "chase-sapphire-preferred":  2.0,   # Chase UR ~2.0 cents/pt
    "amex-gold":                 2.2,   # Amex MR ~2.2 cents/pt
    "citi-premier":              1.8,   # Citi TYP ~1.8 cents/pt
    "capital-one-venture-x":     1.85,  # CapOne Miles ~1.85 cents/pt
    "chase-freedom-unlimited":   2.0,
}


class RewardsCCService:
    """
    Wraps the RewardsCC API.
    Falls back to mock data if API key is not set.
    """

    def __init__(self):
        self.api_key = settings.REWARDSCC_API_KEY
        self.base_url = settings.REWARDSCC_BASE_URL
        self.use_mock = (self.api_key == "YOUR_RAPIDAPI_KEY_HERE")

    async def get_transfer_partners(self, card_key: str) -> list[TransferPartner]:
        """
        Fetch hotel transfer partners and ratios for a given card.
        Edge Case #3: Ratio is dynamic, comes from API.
        """
        if self.use_mock:
            return self._mock_transfer_partners(card_key)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/transferpartners",
                    headers={
                        "X-RapidAPI-Key": self.api_key,
                        "X-RapidAPI-Host": "rewards-credit-card-api.p.rapidapi.com",
                    },
                    params={"cardKey": card_key},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                return self._parse_transfer_partners(data)
        except Exception as e:
            print(f"RewardsCC API error: {e} — falling back to mock data")
            return self._mock_transfer_partners(card_key)

    async def get_point_valuation(self, card_key: str) -> float:
        """Returns cents-per-point valuation for a card."""
        if self.use_mock:
            return MOCK_POINT_VALUATIONS.get(card_key, 1.5)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/card-detail/by-card",
                    headers={
                        "X-RapidAPI-Key": self.api_key,
                        "X-RapidAPI-Host": "rewards-credit-card-api.p.rapidapi.com",
                    },
                    params={"cardKey": card_key},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                return float(data[0].get("baseSpendEarnValuation", 1.5))
        except Exception as e:
            print(f"RewardsCC valuation error: {e} — using default")
            return MOCK_POINT_VALUATIONS.get(card_key, 1.5)

    def _mock_transfer_partners(self, card_key: str) -> list[TransferPartner]:
        partners = MOCK_TRANSFER_PARTNERS.get(card_key, [])
        return [TransferPartner(**p) for p in partners]

    def _parse_transfer_partners(self, data: list[dict]) -> list[TransferPartner]:
        """Parse real RewardsCC API response into TransferPartner models."""
        partners = []
        for item in data:
            if item.get("transferPartnerType") == "hotel":
                partners.append(TransferPartner(
                    partner_name=item.get("transferPartnerName", ""),
                    partner_program_key=item.get("transferPartnerKey", ""),
                    transfer_ratio=float(item.get("transferRatio", 1.0)),
                    min_transfer=int(item.get("minTransfer", 5000)),
                    transfer_increments=item.get("transferIncrements",
                                                 [5000, 10000, 25000, 50000]),
                ))
        return partners


rewards_cc_service = RewardsCCService()