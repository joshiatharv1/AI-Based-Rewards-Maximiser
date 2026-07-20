"""
Mock Credit Card Service:
Simulates a bank API returning user credit card data with points balances.
Architecture is designed so a real bank/aggregator API can be plugged in here.
"""

from app.models.schemas import CreditCard, UserCards, CardStatus
from app.core.config import settings
from typing import Optional
import random

# ─── Mock Database ─────────────────────────────────────────────────────────────
# Simulates what a real bank API would return per user

MOCK_USER_CARDS: dict[str, list[dict]] = {
    "user_001": [
        {
            "card_id": "card_001",
            "card_name": "Chase Sapphire Preferred",
            "issuer": "Chase",
            "card_key": "chase-sapphire-preferred",
            "last_four": "4521",
            "points_balance": 87500,
            "points_currency": "Chase Ultimate Rewards",
            "status": CardStatus.VALID,
            "valid_denominations": [1000, 5000, 10000, 25000, 50000],
        },
        {
            "card_id": "card_002",
            "card_name": "American Express Gold Card",
            "issuer": "American Express",
            "card_key": "amex-gold",
            "last_four": "9873",
            "points_balance": 42000,
            "points_currency": "American Express Membership Rewards",
            "status": CardStatus.VALID,
            "valid_denominations": [1000, 5000, 10000, 25000, 50000],
        },
        {
            "card_id": "card_003",
            "card_name": "Citi Premier Card",
            "issuer": "Citi",
            "card_key": "citi-premier",
            "last_four": "2210",
            "points_balance": 15000,
            "points_currency": "Citi ThankYou Points",
            "status": CardStatus.VALID,
            "valid_denominations": [1000, 5000, 10000, 25000],
        },
    ],
    "user_002": [
        {
            "card_id": "card_004",
            "card_name": "Capital One Venture X",
            "issuer": "Capital One",
            "card_key": "capital-one-venture-x",
            "last_four": "7731",
            "points_balance": 120000,
            "points_currency": "Capital One Miles",
            "status": CardStatus.VALID,
            "valid_denominations": [5000, 10000, 25000, 50000],
        },
        {
            "card_id": "card_005",
            "card_name": "Chase Freedom Unlimited",
            "issuer": "Chase",
            "card_key": "chase-freedom-unlimited",
            "last_four": "3344",
            "points_balance": 8500,
            "points_currency": "Chase Ultimate Rewards",
            "status": CardStatus.VALID,
            "valid_denominations": [1000, 5000, 10000],
        },
    ],
}


class MockCardService:
    """
    Simulates bank API responses.
    Replace methods here with real API calls in production.
    """

    def get_user_cards(self, user_id: str) -> Optional[UserCards]:
        """Fetch all credit cards for a user."""
        raw_cards = MOCK_USER_CARDS.get(user_id)
        if not raw_cards:
            return None
        cards = [CreditCard(**c) for c in raw_cards]
        return UserCards(user_id=user_id, cards=cards)

    def get_card(self, user_id: str, card_id: str) -> Optional[CreditCard]:
        """Fetch a single card for a user."""
        user_cards = self.get_user_cards(user_id)
        if not user_cards:
            return None
        for card in user_cards.cards:
            if card.card_id == card_id:
                return card
        return None

    def validate_card(self, card: CreditCard) -> tuple[bool, str]:
        """
        Edge Case #2: Verify card is from an approved issuer.
        Edge Case #4: Check card status is valid.
        Returns (is_valid, reason)
        """
        if card.issuer not in settings.APPROVED_ISSUERS:
            return False, f"Issuer '{card.issuer}' is not on the approved list."
        if card.status != CardStatus.VALID:
            return False, f"Card ending in {card.last_four} is {card.status.value}."
        return True, "Card is valid."

    def validate_denomination(self, card: CreditCard, points: int) -> tuple[bool, str, int]:
        """
        Edge Case #1: Points must be a valid fixed denomination.
        Returns (is_valid, reason, suggested_denomination)
        """
        valid = card.valid_denominations
        if points in valid:
            return True, "Valid denomination.", points

        # Suggest the nearest valid denomination below requested amount
        lower = [d for d in sorted(valid) if d <= points]
        if lower:
            suggested = max(lower)
            return False, (
                f"{points} is not a valid denomination. "
                f"Valid options: {valid}. "
                f"Suggested: {suggested}"
            ), suggested
        return False, f"Not enough points. Minimum denomination is {min(valid)}.", 0

    def deduct_points(self, user_id: str, card_id: str, points: int) -> bool:
        """Deduct points after confirmed booking (updates mock DB)."""
        raw_cards = MOCK_USER_CARDS.get(user_id, [])
        for card in raw_cards:
            if card["card_id"] == card_id:
                if card["points_balance"] >= points:
                    card["points_balance"] -= points
                    return True
                return False
        return False


mock_card_service = MockCardService()