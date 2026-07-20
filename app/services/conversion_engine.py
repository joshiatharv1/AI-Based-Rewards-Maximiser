"""
Conversion Engine
-----------------
Handles all points math:
- Fetches transfer ratios from RewardsCC
- Validates denominations (Edge Case #1)
- Calculates hotel points received
- Calculates dollar value of points
- Computes cash remainder for split payments
- Optimises points used when points exceed hotel cost
"""

from app.models.schemas import (
    ConversionRequest, ConversionResult,
    BookingPreviewRequest, BookingPreviewResponse,
    PaymentBreakdown, PaymentType
)
from app.services.rewardscc_service import rewards_cc_service
from app.services.card_service import mock_card_service
from fastapi import HTTPException


class ConversionEngine:

    async def get_transfer_partners(self, card_key: str):
        """Return all hotel transfer partners for a card."""
        partners = await rewards_cc_service.get_transfer_partners(card_key)
        if not partners:
            raise HTTPException(
                status_code=404,
                detail=f"No hotel transfer partners found for card: {card_key}"
            )
        return partners

    async def convert_points(
        self,
        request: ConversionRequest,
        user_id: str,
    ) -> ConversionResult:
        """
        Core conversion logic.
        Validates denomination, fetches ratio, computes hotel points + dollar value.
        """
        card = mock_card_service.get_card(user_id, request.card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found.")

        # Edge Case #1: Validate fixed denomination
        is_valid, reason, suggested = mock_card_service.validate_denomination(
            card, request.points_to_use
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=reason)

        # Check sufficient balance
        if card.points_balance < request.points_to_use:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient points. Balance: {card.points_balance:,}, "
                    f"Requested: {request.points_to_use:,}"
                )
            )

        # Fetch transfer partners + find matching one
        partners = await rewards_cc_service.get_transfer_partners(request.card_key)
        partner = next(
            (p for p in partners
             if p.partner_program_key == request.hotel_loyalty_program
             or p.partner_name == request.hotel_loyalty_program),
            None
        )
        if not partner:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No transfer partnership between {card.card_name} "
                    f"and {request.hotel_loyalty_program}."
                )
            )

        # Edge Case #3: Dynamic ratio from API
        ratio = partner.transfer_ratio
        hotel_points = int(request.points_to_use * ratio)

        # Dollar value of points used
        valuation_cents = await rewards_cc_service.get_point_valuation(request.card_key)
        dollar_value = round((request.points_to_use * valuation_cents) / 100, 2)

        return ConversionResult(
            card_id               = request.card_id,
            card_key              = request.card_key,
            points_used           = request.points_to_use,
            transfer_ratio        = ratio,
            hotel_points_received = hotel_points,
            hotel_program         = partner.partner_name,
            points_dollar_value   = dollar_value,
            remaining_card_points = card.points_balance - request.points_to_use,
        )

    async def build_payment_breakdown(
        self,
        preview_request: BookingPreviewRequest,
    ) -> BookingPreviewResponse:
        """
        Edge Case #4: Full payment breakdown with tax, fees, points discount, cash remainder.

        Key fix: when points value exceeds the hotel cost, we find the smallest
        valid denomination that still covers the bill — so the user doesn't burn
        more points than necessary. The excess is shown as points saved.
        """
        hotel        = preview_request.hotel_offer
        result       = preview_request.conversion_result
        hotel_cost   = hotel.total_price
        points_value = result.points_dollar_value

        # cents per point for this card
        valuation_cents = (result.points_dollar_value / result.points_used * 100) \
            if result.points_used > 0 else 200.0  # 2.0 cpp default

        if points_value >= hotel_cost:
            # Points more than cover the cost — find the minimum denomination needed
            payment_type   = PaymentType.POINTS_ONLY
            cash_remainder = 0.0

            card = mock_card_service.get_card(
                preview_request.user_id, preview_request.card_id
            )
            valid_denoms = sorted(card.valid_denominations) if card else [5000]

            # Walk up denominations until we find the smallest one that covers the bill
            optimal_points = result.points_used  # fallback
            for d in valid_denoms:
                if (d * valuation_cents / 100) >= hotel_cost:
                    optimal_points = d
                    break

            final_points_used  = optimal_points
            # Show only what the hotel actually charged, not the full transferred value.
            # e.g. 50,000 pts worth $1000 toward a $693.92 hotel → display $693.92 applied
            final_points_value = hotel_cost

        elif preview_request.points_to_use == 0:
            payment_type       = PaymentType.CASH_ONLY
            cash_remainder     = hotel_cost
            final_points_used  = 0
            final_points_value = 0.0

        else:
            # Split payment — points cover part, user pays the rest in cash
            payment_type       = PaymentType.SPLIT
            cash_remainder     = max(0.0, round(hotel_cost - points_value, 2))
            final_points_used  = result.points_used
            final_points_value = points_value

        breakdown = PaymentBreakdown(
            room_subtotal       = hotel.room_subtotal,
            taxes               = hotel.taxes,
            resort_fees         = hotel.resort_fees,
            total_before_points = hotel_cost,
            points_used         = final_points_used,
            points_dollar_value = final_points_value,
            cash_remainder      = cash_remainder,
            payment_type        = payment_type,
        )

        return BookingPreviewResponse(
            hotel_name            = hotel.hotel_name,
            check_in              = "",
            check_out             = "",
            loyalty_program       = result.hotel_program,
            transfer_ratio        = result.transfer_ratio,
            points_used           = final_points_used,
            hotel_points_received = result.hotel_points_received,
            breakdown             = breakdown,
            ready_to_confirm      = True,
        )


conversion_engine = ConversionEngine()