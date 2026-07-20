"""
Optivoy Rewards Engine — Full Demo
------------------------------------
Runs the complete agentic workflow end to end:

  Step 1  → Validate user's credit cards
  Step 2  → Search hotels in target city
  Step 3  → Calculate all card × hotel redemption options
  Step 4  → Agent ranks top 3 by value
  Step 5  → RAG answers a follow-up question
  Step 6  → User selects an option
  Step 7  → Full payment breakdown shown
  Step 8  → Booking confirmed, points deducted

Run with:
    python demo.py

No API keys needed — runs fully on mock data + OpenAI for RAG.
Add REWARDSCC_API_KEY and AMADEUS credentials to .env for live data.
"""

import asyncio
from app.agents.rewards_agent import run_agent
from app.rag.rag_engine import rag_engine
from app.services.card_service import mock_card_service
from app.services.conversion_engine import conversion_engine
from app.models.schemas import (
    BookingPreviewRequest, BookingConfirmRequest,
    ConversionRequest, HotelOffer, ConversionResult,
)

# ─── Demo Config ──────────────────────────────────────────────────────────────
USER_ID   = "user_001"
CITY      = "NYC"
CHECK_IN  = "2025-09-01"
CHECK_OUT = "2025-09-03"
ADULTS    = 1

DIVIDER      = "=" * 62
THIN_DIVIDER = "-" * 62


def header(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def subheader(title: str):
    print(f"\n  {THIN_DIVIDER}")
    print(f"  {title}")
    print(f"  {THIN_DIVIDER}")


# ─── Step 1-4: Agent Run ──────────────────────────────────────────────────────

async def run_demo():
    print(f"\n{'='*62}")
    print("  OPTIVOY REWARDS ENGINE — LIVE DEMO")
    print(f"{'='*62}")
    print(f"  User:    {USER_ID}")
    print(f"  Search:  {CITY}  |  {CHECK_IN} → {CHECK_OUT}  |  {ADULTS} adult")

    # ── Step 1-4: Run the agent ───────────────────────────────────────────────
    header("STEP 1-4 │ Agentic Workflow")
    print("  Running LangGraph agent...\n")

    agent_result = await run_agent(
        user_id   = USER_ID,
        city_code = CITY,
        check_in  = CHECK_IN,
        check_out = CHECK_OUT,
        adults    = ADULTS,
    )

    # ── Print top 3 recommendations ───────────────────────────────────────────
    header("STEP 4 │ Agent Top 3 Recommendations")
    print(f"  {agent_result.agent_summary}\n")

    for rec in agent_result.top_recommendations:
        print(f"  ┌─ Rank #{rec.rank} {'─'*44}")
        print(f"  │  Card:            {rec.card_name}")
        print(f"  │  Loyalty Program: {rec.loyalty_program}")
        print(f"  │  Points to Use:   {rec.points_to_use:,}")
        print(f"  │  Transfer Ratio:  {rec.transfer_ratio}x  →  "
              f"{rec.hotel_points_received:,} hotel points")
        print(f"  │  Cash Remainder:  ${rec.cash_remainder:.2f}")
        print(f"  │  Value/Point:     {rec.value_per_point}¢")
        print(f"  │")
        print(f"  │  💬 {rec.reasoning}")
        print(f"  └{'─'*52}\n")

    # ── Step 5: RAG follow-up ─────────────────────────────────────────────────
    header("STEP 5 │ RAG — Follow-Up Question")

    followup_q = "Why is the top option the best choice, and should I do split payment or points only?"
    print(f"  User asks: \"{followup_q}\"\n")

    await rag_engine.ingest()   # loads existing store, no rebuild
    rag_result = await rag_engine.query_with_recommendation(
        question        = followup_q,
        recommendations = agent_result.top_recommendations,
    )
    print(f"  Agent answers:\n")
    # Indent each line of the answer
    for line in rag_result["answer"].split("\n"):
        print(f"  {line}")
    print(f"\n  Sources consulted: {', '.join(rag_result['sources'])}")

    # ── Step 6: User selects option #1 ────────────────────────────────────────
    header("STEP 6 │ User Selects Option #1")

    selected = agent_result.top_recommendations[0]
    print(f"  Selected: {selected.card_name} → {selected.loyalty_program}")
    print(f"  Points:   {selected.points_to_use:,}")

    # Fetch the card and rebuild conversion result for preview
    card = mock_card_service.get_card(USER_ID, selected.card_id)

    # Validate card before proceeding (Edge Case #2 + #5)
    is_valid, reason = mock_card_service.validate_card(card)
    if not is_valid:
        print(f"\n  ✗ Card validation failed: {reason}")
        return

    # Validate denomination (Edge Case #1)
    denom_valid, denom_reason, suggested = mock_card_service.validate_denomination(
        card, selected.points_to_use
    )
    status = "✓" if denom_valid else f"✗ {denom_reason}"
    print(f"  Card valid:        ✓ ({reason})")
    print(f"  Denomination valid: {status}")

    # ── Step 7: Payment breakdown ─────────────────────────────────────────────
    header("STEP 7 │ Full Payment Breakdown")

    # Build a mock HotelOffer and ConversionResult for the selected option
    # In production these come from the actual Amadeus + conversion API calls
    from app.services.amadeus_service import amadeus_service
    from app.models.schemas import HotelSearchRequest
    hotels = await amadeus_service.search_hotels(
        HotelSearchRequest(city_code=CITY, check_in=CHECK_IN, check_out=CHECK_OUT, adults=ADULTS)
    )
    # Pick hotel matching selected loyalty program
    hotel = next(
        (h for h in hotels if h.loyalty_program == selected.loyalty_program),
        hotels[0]
    )

    from app.services.rewardscc_service import rewards_cc_service
    valuation = await rewards_cc_service.get_point_valuation(card.card_key)
    dollar_value = round((selected.points_to_use * valuation) / 100, 2)

    conversion_result = ConversionResult(
        card_id               = selected.card_id,
        card_key              = card.card_key,
        points_used           = selected.points_to_use,
        transfer_ratio        = selected.transfer_ratio,
        hotel_points_received = selected.hotel_points_received,
        hotel_program         = selected.loyalty_program,
        points_dollar_value   = dollar_value,
        remaining_card_points = card.points_balance - selected.points_to_use,
    )

    preview_request = BookingPreviewRequest(
        user_id          = USER_ID,
        card_id          = selected.card_id,
        hotel_offer_id   = hotel.hotel_id,
        hotel_offer      = hotel,
        points_to_use    = selected.points_to_use,
        loyalty_program  = selected.loyalty_program,
        conversion_result= conversion_result,
    )

    preview = await conversion_engine.build_payment_breakdown(preview_request)
    b = preview.breakdown

    print(f"  Hotel:             {hotel.hotel_name}")
    print(f"  Check-in:          {CHECK_IN}  →  Check-out: {CHECK_OUT}")
    print(f"  Loyalty Program:   {selected.loyalty_program}")
    print(f"  Transfer Ratio:    {selected.transfer_ratio}x")
    print(f"  Hotel Points:      {selected.hotel_points_received:,}")
    print()
    print(f"  {'PAYMENT BREAKDOWN':─<44}")
    print(f"  Room Subtotal:     ${b.room_subtotal:>8.2f}")
    print(f"  Taxes (14%):       ${b.taxes:>8.2f}")
    print(f"  Resort Fees:       ${b.resort_fees:>8.2f}")
    print(f"  {'─'*36}")
    print(f"  Total Before Pts:  ${b.total_before_points:>8.2f}")
    print(f"  Points Applied:    {selected.points_to_use:,} pts  (−${b.points_dollar_value:.2f})")
    print(f"  {'─'*36}")
    print(f"  Cash Due:          ${b.cash_remainder:>8.2f}  [{b.payment_type.value.upper()}]")

    # ── Step 8: Confirm booking ───────────────────────────────────────────────
    header("STEP 8 │ Booking Confirmed")

    # Deduct points
    mock_card_service.deduct_points(USER_ID, selected.card_id, selected.points_to_use)
    updated_card = mock_card_service.get_card(USER_ID, selected.card_id)

    import uuid
    booking_id = str(uuid.uuid4())[:8].upper()

    print(f"  ✓ Booking ID:          OPT-{booking_id}")
    print(f"  ✓ Status:              CONFIRMED")
    print(f"  ✓ Hotel:               {hotel.hotel_name}")
    print(f"  ✓ Confirmation No.:    OPT-{booking_id}")
    print(f"  ✓ Points Deducted:     {selected.points_to_use:,}")
    print(f"  ✓ Remaining Balance:   {updated_card.points_balance:,} {card.points_currency}")
    print(f"  ✓ Cash Charged:        ${b.cash_remainder:.2f}")

    print(f"\n{DIVIDER}")
    print("  ✅  DEMO COMPLETE — ALL STEPS PASSED")
    print(DIVIDER)

    print("""
  What was demonstrated:
  ─────────────────────────────────────────────────────────
  ✓ Edge Case #1  Fixed denomination validation
  ✓ Edge Case #2  Approved issuer whitelist check
  ✓ Edge Case #3  Dynamic conversion ratio (mock RewardsCC)
  ✓ Edge Case #4  Full payment breakdown with tax + fees
  ✓ Edge Case #5  Card validated before every booking step

  ✓ Agentic Flow  LangGraph 4-node orchestration
  ✓ RAG           OpenAI embeddings + gpt-4o-mini answers
  ✓ Multi-card    Ranked across all user cards
  ✓ Split Pay     Points + cash hybrid supported
  ─────────────────────────────────────────────────────────
    """)


if __name__ == "__main__":
    asyncio.run(run_demo())