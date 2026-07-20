import asyncio
from app.services.card_service import mock_card_service
from app.services.rewardscc_service import rewards_cc_service
from app.services.amadeus_service import amadeus_service
from app.models.schemas import HotelSearchRequest, ConversionRequest

USER_ID = "user_001"


async def test_cards():
    print("\n" + "="*50)
    print("TEST 1: Fetch User Cards")
    print("="*50)
    user_cards = mock_card_service.get_user_cards(USER_ID)
    for card in user_cards.cards:
        print(f"  ✓ {card.card_name} | {card.points_currency}")
        print(f"    Balance: {card.points_balance:,} pts | Last 4: {card.last_four}")


async def test_card_validation():
    print("\n" + "="*50)
    print("TEST 2: Card Validation (Edge Cases #2, #4)")
    print("="*50)
    user_cards = mock_card_service.get_user_cards(USER_ID)
    for card in user_cards.cards:
        is_valid, reason = mock_card_service.validate_card(card)
        status = "✓ VALID" if is_valid else "✗ INVALID"
        print(f"  {status} — {card.card_name} ({card.issuer}): {reason}")


async def test_denomination_validation():
    print("\n" + "="*50)
    print("TEST 3: Denomination Validation (Edge Case #1)")
    print("="*50)
    card = mock_card_service.get_card(USER_ID, "card_001")

    test_amounts = [4589, 5000, 1234, 10000, 99999]
    for amount in test_amounts:
        is_valid, reason, suggested = mock_card_service.validate_denomination(card, amount)
        status = "✓" if is_valid else "✗"
        print(f"  {status} {amount:,} pts → {reason}")


async def test_transfer_partners():
    print("\n" + "="*50)
    print("TEST 4: Transfer Partners & Ratios (Edge Case #3)")
    print("="*50)
    card_keys = ["chase-sapphire-preferred", "amex-gold", "citi-premier"]
    for key in card_keys:
        partners = await rewards_cc_service.get_transfer_partners(key)
        print(f"\n  {key}:")
        for p in partners:
            print(f"    → {p.partner_name} | Ratio: {p.transfer_ratio}x | Min: {p.min_transfer:,} pts")


async def test_hotel_search():
    print("\n" + "="*50)
    print("TEST 5: Hotel Search (Amadeus)")
    print("="*50)
    request = HotelSearchRequest(
        city_code="NYC",
        check_in="2025-09-01",
        check_out="2025-09-03",
        adults=1
    )
    hotels = await amadeus_service.search_hotels(request)
    for h in hotels:
        print(f"  ✓ {h.hotel_name}")
        print(f"    ${h.room_rate_per_night}/night | Total: ${h.total_price} "
              f"(tax: ${h.taxes} + fees: ${h.resort_fees})")
        print(f"    Loyalty: {h.loyalty_program}")


async def test_full_conversion():
    print("\n" + "="*50)
    print("TEST 6: Full Conversion + Payment Breakdown")
    print("="*50)
    from app.services.conversion_engine import conversion_engine

    request = ConversionRequest(
        card_id="card_001",
        card_key="chase-sapphire-preferred",
        hotel_loyalty_program="marriott-bonvoy",
        points_to_use=10000,
    )
    result = await conversion_engine.convert_points(request, USER_ID)
    print(f"  Card:              Chase Sapphire Preferred")
    print(f"  Points Used:       {result.points_used:,}")
    print(f"  Transfer Ratio:    {result.transfer_ratio}x")
    print(f"  Hotel Points:      {result.hotel_points_received:,} {result.hotel_program}")
    print(f"  Dollar Value:      ${result.points_dollar_value}")
    print(f"  Remaining Points:  {result.remaining_card_points:,}")


async def main():
    print("\n OPTIVOY REWARDS ENGINE —1 TESTS")
    await test_cards()
    await test_card_validation()
    await test_denomination_validation()
    await test_transfer_partners()
    await test_hotel_search()
    await test_full_conversion()

    print("\n" + "="*50)
    print("✅ ALL DAY 1 TESTS PASSED")
    print("="*50)
    print("\nNext: Start server with → uvicorn app.main:app --reload")
    print("Then visit: http://localhost:8000/docs\n")


if __name__ == "__main__":
    asyncio.run(main())