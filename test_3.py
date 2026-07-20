"""
Day 3 Test Script — RAG Knowledge Base
---------------------------------------
Tests the full RAG pipeline:
1. Ingests knowledge base into ChromaDB
2. Runs sample queries
3. Tests follow-up questions on agent recommendations

Run with: python test_day3.py
Requires: OPENAI_API_KEY in .env
"""

import asyncio
from app.rag.rag_engine import rag_engine
from app.models.schemas import AgentRecommendation


# Sample recommendations (as if agent just ran)
SAMPLE_RECOMMENDATIONS = [
    AgentRecommendation(
        rank=1,
        card_id="card_001",
        card_name="Chase Sapphire Preferred",
        loyalty_program="Marriott Bonvoy",
        points_to_use=50000,
        hotel_points_received=50000,
        transfer_ratio=1.0,
        cash_remainder=0.0,
        value_per_point=2.0,
        reasoning="Best value: 50,000 Chase UR → 50,000 Marriott points, covers full stay."
    ),
    AgentRecommendation(
        rank=2,
        card_id="card_002",
        card_name="American Express Gold Card",
        loyalty_program="Hilton Honors",
        points_to_use=25000,
        hotel_points_received=50000,
        transfer_ratio=2.0,
        cash_remainder=43.60,
        value_per_point=2.2,
        reasoning="Strong alternative: 25,000 Amex MR → 50,000 Hilton points, $43.60 cash."
    ),
    AgentRecommendation(
        rank=3,
        card_id="card_003",
        card_name="Citi Premier Card",
        loyalty_program="Marriott Bonvoy",
        points_to_use=10000,
        hotel_points_received=10000,
        transfer_ratio=1.0,
        cash_remainder=513.92,
        value_per_point=1.8,
        reasoning="Backup: 10,000 Citi TYP → 10,000 Marriott points, $513.92 cash."
    ),
]


async def test_ingest():
    print("\n" + "="*60)
    print("TEST 1: Ingest Knowledge Base")
    print("="*60)
    count = await rag_engine.ingest(force_rebuild=True)
    print(f"Result: {count} chunks ingested into ChromaDB")


async def test_card_questions():
    print("\n" + "="*60)
    print("TEST 2: Card-Specific Questions")
    print("="*60)

    questions = [
        "Which card is best for Marriott Bonvoy transfers?",
        "What is a good cents per point value for hotel redemptions?",
        "Should I use Amex Gold or Chase Sapphire for Hilton?",
    ]

    for q in questions:
        print(f"\n  Q: {q}")
        result = await rag_engine.query(q)
        print(f"  A: {result['answer']}")
        print(f"  Sources: {result['sources']}")


async def test_with_user_context():
    print("\n" + "="*60)
    print("TEST 3: Query With User Context")
    print("="*60)

    user_context = {
        "cards": ["Chase Sapphire Preferred", "American Express Gold Card"],
        "balances": {
            "Chase Sapphire Preferred": 87500,
            "American Express Gold Card": 42000,
        },
        "hotel": "Marriott Marquis Times Square",
    }

    question = "Which of my cards should I use for this Marriott stay?"
    print(f"\n  Q: {question}")
    print(f"  Context: {user_context['cards']} | Hotel: {user_context['hotel']}")

    result = await rag_engine.query(question, user_context=user_context)
    print(f"\n  A: {result['answer']}")


async def test_followup_on_recommendations():
    print("\n" + "="*60)
    print("TEST 4: Follow-Up Questions on Agent Recommendations")
    print("="*60)

    followups = [
        "Why is option 1 better than option 3?",
        "Is 2 cents per point a good value?",
        "Should I do split payment or points only?",
    ]

    for q in followups:
        print(f"\n  Q: {q}")
        result = await rag_engine.query_with_recommendation(
            question=q,
            recommendations=SAMPLE_RECOMMENDATIONS,
        )
        print(f"  A: {result['answer']}")


async def main():
    print("\n🧠 OPTIVOY RAG ENGINE — DAY 3 TESTS")
    print("Using OpenAI text-embedding-3-small + gpt-4o-mini\n")

    await test_ingest()
    await test_card_questions()
    await test_with_user_context()
    await test_followup_on_recommendations()

    print("\n" + "="*60)
    print("✅ ALL DAY 3 TESTS COMPLETE")
    print("="*60)
    print("\nRAG is now integrated. Full flow:")
    print("  1. POST /api/agent/recommend  → get top 3 options")
    print("  2. POST /api/rag/query        → ask any card/hotel question")
    print("  3. POST /api/rag/followup     → ask follow-ups on recommendations\n")


if __name__ == "__main__":
    asyncio.run(main())