from fastapi import APIRouter, HTTPException
from app.services.card_service import mock_card_service
from app.models.schemas import UserCards, CreditCard

router = APIRouter()

@router.get("/{user_id}", response_model=UserCards)
async def get_user_cards(user_id: str):
    """Get all credit cards for a user."""
    result = mock_card_service.get_user_cards(user_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No cards found for user {user_id}")
    return result

@router.get("/{user_id}/{card_id}/validate")
async def validate_card(user_id: str, card_id: str):
    """Validate a specific card (Edge Cases #2 and #4)."""
    card = mock_card_service.get_card(user_id, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")
    is_valid, reason = mock_card_service.validate_card(card)
    return {
        "card_id":   card_id,
        "card_name": card.card_name,
        "issuer":    card.issuer,
        "is_valid":  is_valid,
        "reason":    reason,
        "balance":   card.points_balance,
        "currency":  card.points_currency,
    }

@router.get("/{user_id}/{card_id}/denominations")
async def get_valid_denominations(user_id: str, card_id: str):
    """Get valid point denominations for a card (Edge Case #1)."""
    card = mock_card_service.get_card(user_id, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")
    return {
        "card_id":             card_id,
        "card_name":           card.card_name,
        "valid_denominations": card.valid_denominations,
        "current_balance":     card.points_balance,
    }