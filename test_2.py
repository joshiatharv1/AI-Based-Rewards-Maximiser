"""
Day 2 Test Script — LangGraph Agent
------------------------------------
Tests the full agentic workflow end to end.
Run with: python test_day2.py
"""

import asyncio
from app.agents.rewards_agent import run_agent


async def test_agent_full_run():
    print("\n" + "="*60)
    print("OPTIVOY REWARDS AGENT — FULL RUN")
    print("="*60)
    print("User:     user_001 (3 cards: Chase Sapphire, Amex Gold, Citi Premier)")
    print("Search:   New York City | Sep 1–3, 2025 | 1 adult")
    print("="*60)

    result = await run_agent(
        user_id   = "user_001",
        city_code = "NYC",
        check_in  = "2025-09-01",
        check_out = "2025-09-03",
        adults    = 1,
    )

    print("\n" + "="*60)
    print("AGENT SUMMARY")
    print("="*60)
    print(result.agent_summary)

    print("\n" + "="*60)
    print("TOP 3 RECOMMENDATIONS")
    print("="*60)

    for rec in result.top_recommendations:
        print(f"\n  Rank #{rec.rank}")
        print(f"  Card:              {rec.card_name}")
        print(f"  Loyalty Program:   {rec.loyalty_program}")
        print(f"  Points to Use:     {rec.points_to_use:,}")
        print(f"  Transfer Ratio:    {rec.transfer_ratio}x")
        print(f"  Hotel Points:      {rec.hotel_points_received:,}")
        print(f"  Cash Remainder:    ${rec.cash_remainder}")
        print(f"  Value Per Point:   {rec.value_per_point}¢")
        print(f"\n  💬 Agent Reasoning:")
        print(f"  {rec.reasoning}")

    print("\n" + "="*60)
    print("✅ AGENT TEST COMPLETE")
    print("="*60)


async def test_agent_user2():
    print("\n\n" + "="*60)
    print("AGENT RUN — USER 002 (Capital One + Chase Freedom)")
    print("="*60)

    result = await run_agent(
        user_id   = "user_002",
        city_code = "NYC",
        check_in  = "2025-09-01",
        check_out = "2025-09-03",
    )

    print(f"\nSummary: {result.agent_summary}")
    for rec in result.top_recommendations:
        print(f"\n  #{rec.rank} — {rec.card_name} → {rec.loyalty_program}")
        print(f"  {rec.reasoning}")


async def main():
    await test_agent_full_run()
    await test_agent_user2()


if __name__ == "__main__":
    asyncio.run(main())