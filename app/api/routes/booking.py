from fastapi import APIRouter, HTTPException
from app.services.conversion_engine import conversion_engine
from app.services.card_service import mock_card_service
from app.models.schemas import (
    BookingPreviewRequest, BookingPreviewResponse,
    BookingConfirmRequest, BookingConfirmResponse,
    PaymentBreakdown, PaymentType
)
import uuid

router = APIRouter()

@router.post("/preview", response_model=BookingPreviewResponse)
async def booking_preview(request: BookingPreviewRequest):
    """
    Generate full payment breakdown before confirming.
    Edge Case #4: Shows room rate, taxes, fees, points value, cash remainder.
    """
    # Edge Case #2 + #5: Validate card before proceeding
    card = mock_card_service.get_card(request.user_id, request.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")

    is_valid, reason = mock_card_service.validate_card(card)
    if not is_valid:
        raise HTTPException(status_code=403, detail=reason)

    return await conversion_engine.build_payment_breakdown(request)


@router.post("/confirm", response_model=BookingConfirmResponse)
async def confirm_booking(request: BookingConfirmRequest):
    """
    Confirm booking after user reviews preview.
    Deducts points from card balance.
    """
    # Validate card one final time
    card = mock_card_service.get_card(request.user_id, request.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")

    is_valid, reason = mock_card_service.validate_card(card)
    if not is_valid:
        raise HTTPException(status_code=403, detail=reason)

    # Deduct points
    success = mock_card_service.deduct_points(
        request.user_id, request.card_id, request.points_to_use
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to deduct points. Check balance.")

    # In production: call Amadeus booking API here
    # POST /v2/booking/hotel-orders

    booking_id = str(uuid.uuid4())[:8].upper()

    return BookingConfirmResponse(
        booking_id           = booking_id,
        status               = "CONFIRMED",
        hotel_name           = f"Hotel {request.hotel_offer_id}",
        confirmation_number  = f"OPT-{booking_id}",
        breakdown            = PaymentBreakdown(
            room_subtotal       = 0,
            taxes               = 0,
            resort_fees         = 0,
            total_before_points = 0,
            points_used         = request.points_to_use,
            points_dollar_value = 0,
            cash_remainder      = 0,
            payment_type        = PaymentType.SPLIT,
        ),
    )