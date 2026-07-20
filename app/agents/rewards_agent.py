"""
Optivoy Rewards Agent — LangGraph Orchestrator
------------------------------------------------
Agentic workflow that:
1. Validates all user cards
2. Searches hotels
3. Fetches transfer partners for each card
4. Calculates conversion + payment breakdown for every card × hotel program combo
5. Ranks top 3 options by value per point
6. Returns plain English reasoning for each recommendation

Uses LangGraph StateGraph for step-by-step orchestration.
"""

from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
import operator

from app.services.card_service import mock_card_service
from app.services.rewardscc_service import rewards_cc_service
from app.services.amadeus_service import amadeus_service
from app.models.schemas import (
    CreditCard, HotelOffer, HotelSearchRequest,
    ConversionRequest, AgentRecommendation, AgentResponse,
    TransferPartner,
)
from app.services.conversion_engine import conversion_engine


# ─── Agent State ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    # Inputs
    user_id:      str
    city_code:    str
    check_in:     str
    check_out:    str
    adults:       int

    # Intermediate state
    valid_cards:  List[CreditCard]
    hotels:       List[HotelOffer]
    errors:       Annotated[List[str], operator.add]

    # Output
    recommendations: List[AgentRecommendation]
    agent_summary:   str
    selected_hotel:  Optional[HotelOffer]
    _raw_options:    List[dict]


# ─── Node 1: Validate Cards ───────────────────────────────────────────────────

async def validate_cards_node(state: AgentState) -> dict:
    """
    Fetches all user cards and filters to valid, approved ones.
    Edge Cases #2 and #4.
    """
    print("\n[Agent] Step 1: Validating credit cards...")

    user_cards = mock_card_service.get_user_cards(state["user_id"])
    if not user_cards or not user_cards.cards:
        return {
            "valid_cards": [],
            "errors": [f"No cards found for user {state['user_id']}"]
        }

    valid_cards = []
    for card in user_cards.cards:
        is_valid, reason = mock_card_service.validate_card(card)
        if is_valid:
            valid_cards.append(card)
            print(f"  ✓ {card.card_name} — {card.points_balance:,} pts")
        else:
            print(f"  ✗ {card.card_name} — {reason}")

    return {"valid_cards": valid_cards}


# ─── Node 2: Search Hotels ────────────────────────────────────────────────────

async def search_hotels_node(state: AgentState) -> dict:
    """Searches available hotels via Amadeus."""
    print("\n[Agent] Step 2: Searching hotels...")

    request = HotelSearchRequest(
        city_code=state["city_code"],
        check_in=state["check_in"],
        check_out=state["check_out"],
        adults=state["adults"],
    )
    hotels = await amadeus_service.search_hotels(request)
    print(f"  Found {len(hotels)} hotels in {state['city_code']}")
    for h in hotels:
        print(f"  → {h.hotel_name} | ${h.total_price} total | {h.loyalty_program}")

    return {"hotels": hotels}


# ─── Node 3: Calculate All Options ────────────────────────────────────────────

async def calculate_options_node(state: AgentState) -> dict:
    """
    For every valid card × hotel loyalty program combination:
    - Fetches dynamic transfer ratio (Edge Case #3)
    - Validates best denomination (Edge Case #1)
    - Calculates hotel points, dollar value, cash remainder
    Builds raw scored options list.
    """
    print("\n[Agent] Step 3: Calculating all redemption options...")

    options = []

    for card in state["valid_cards"]:
        partners = await rewards_cc_service.get_transfer_partners(card.card_key)
        valuation = await rewards_cc_service.get_point_valuation(card.card_key)

        for hotel in state["hotels"]:
            # Find a transfer partner matching this hotel's loyalty program
            # Case-insensitive match so naming variations don't break the join
            hotel_prog_lower = hotel.loyalty_program.lower()
            partner = next(
                (p for p in partners
                 if p.partner_name.lower() == hotel_prog_lower
                 or hotel_prog_lower in p.partner_name.lower()
                 or p.partner_name.lower() in hotel_prog_lower),
                None
            )
            if not partner:
                continue  # This card has no partnership with this hotel program

            # Find the best valid denomination ≤ card balance
            best_denomination = _best_denomination(
                card.points_balance,
                card.valid_denominations,
                partner.transfer_increments,
            )
            if best_denomination == 0:
                continue  # Not enough points for any denomination

            # Calculate conversion
            hotel_points = int(best_denomination * partner.transfer_ratio)
            dollar_value = round((best_denomination * valuation) / 100, 2)
            cash_remainder = max(0.0, round(hotel.total_price - dollar_value, 2))
            value_per_point = round(valuation, 4)  # cents per point

            options.append({
                "card":             card,
                "hotel":            hotel,
                "partner":          partner,
                "denomination":     best_denomination,
                "hotel_points":     hotel_points,
                "dollar_value":     dollar_value,
                "cash_remainder":   cash_remainder,
                "value_per_point":  value_per_point,
            })

            print(
                f"  {card.card_name} → {hotel.loyalty_program} | "
                f"{best_denomination:,} pts → ${dollar_value} value | "
                f"Cash left: ${cash_remainder}"
            )

    return {"recommendations": options, "_raw_options": options}  # raw — ranked in next node


# ─── Node 4: Rank Top 3 ───────────────────────────────────────────────────────

async def rank_recommendations_node(state: AgentState) -> dict:
    """
    Ranks all options by a composite score:
      - Primary:   value per point (higher = better)
      - Secondary: lower cash remainder (less out of pocket)
    Returns top 3 with plain English reasoning.
    """
    print("\n[Agent] Step 4: Ranking top 3 recommendations...")

    raw = state["recommendations"]
    if not raw:
        return {
            "recommendations": [],
            "agent_summary": "No redemption options found. Your cards may not have transfer partnerships with available hotels, or your points balance may be insufficient.",
        }

    # Score: weighted composite
    def score(opt):
        return (opt["value_per_point"] * 0.6) + ((1 / max(opt["cash_remainder"], 1)) * 0.4)

    ranked = sorted(raw, key=score, reverse=True)[:3]

    recommendations = []
    for i, opt in enumerate(ranked, 1):
        card    = opt["card"]
        hotel   = opt["hotel"]
        partner = opt["partner"]

        reasoning = _build_reasoning(i, opt)
        print(f"\n  #{i} — {card.card_name} → {hotel.hotel_name}")
        print(f"       {reasoning}")

        recommendations.append(AgentRecommendation(
            rank                 = i,
            card_id              = card.card_id,
            card_name            = card.card_name,
            loyalty_program      = partner.partner_name,
            points_to_use        = opt["denomination"],
            hotel_points_received= opt["hotel_points"],
            transfer_ratio       = partner.transfer_ratio,
            cash_remainder       = opt["cash_remainder"],
            value_per_point      = opt["value_per_point"],
            reasoning            = reasoning,
        ))

    summary = (
        f"I found {len(raw)} possible redemption combinations across your "
        f"{len(state['valid_cards'])} card(s) and {len(state['hotels'])} hotel(s). "
        f"Here are the top 3 options ranked by point value. "
        f"Option #1 gives you the best cents-per-point return."
    )

    return {
        "recommendations": recommendations,
        "agent_summary":   summary,
    }


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _best_denomination(
    balance: int,
    card_denoms: List[int],
    partner_denoms: List[int],
) -> int:
    """
    Edge Case #1: Find the highest valid denomination that:
    - Is in the card's valid denominations
    - Is in the partner's transfer increments
    - Is ≤ the card's current balance
    """
    valid = sorted(
        set(card_denoms) & set(partner_denoms),
        reverse=True
    )
    for d in valid:
        if balance >= d:
            return d
    return 0


def _build_reasoning(rank: int, opt: dict) -> str:
    """Generate plain English explanation for a recommendation."""
    card    = opt["card"]
    hotel   = opt["hotel"]
    partner = opt["partner"]

    prefix = {1: "Best value", 2: "Strong alternative", 3: "Solid backup"}[rank]

    return (
        f"{prefix}: Use {opt['denomination']:,} {card.points_currency} from your "
        f"{card.card_name} (ending {card.last_four}). "
        f"At a {partner.transfer_ratio}x transfer ratio, that becomes "
        f"{opt['hotel_points']:,} {partner.partner_name} points, worth ~${opt['dollar_value']} "
        f"toward a stay at {hotel.hotel_name} (total ${hotel.total_price}). "
        f"You'd pay ${opt['cash_remainder']} in cash for the remainder. "
        f"Value: {opt['value_per_point']}¢ per point."
    )


# ─── Build the Graph ──────────────────────────────────────────────────────────

def build_agent() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("validate_cards",      validate_cards_node)
    graph.add_node("search_hotels",       search_hotels_node)
    graph.add_node("calculate_options",   calculate_options_node)
    graph.add_node("rank_recommendations",rank_recommendations_node)

    graph.set_entry_point("validate_cards")
    graph.add_edge("validate_cards",       "search_hotels")
    graph.add_edge("search_hotels",        "calculate_options")
    graph.add_edge("calculate_options",    "rank_recommendations")
    graph.add_edge("rank_recommendations", END)

    return graph.compile()


# Singleton agent
rewards_agent = build_agent()


# ─── Public Run Function ──────────────────────────────────────────────────────

async def run_agent(
    user_id:   str,
    city_code: str,
    check_in:  str,
    check_out: str,
    adults:    int = 1,
) -> AgentResponse:
    """
    Entry point for the agent.
    Returns top 3 redemption recommendations + summary.
    """
    initial_state: AgentState = {
        "user_id":         user_id,
        "city_code":       city_code,
        "check_in":        check_in,
        "check_out":       check_out,
        "adults":          adults,
        "valid_cards":     [],
        "hotels":          [],
        "errors":          [],
        "recommendations": [],
        "agent_summary":   "",
        "selected_hotel":  None,
        "_raw_options":    [],
    }

    final_state = await rewards_agent.ainvoke(initial_state)

    # Pick representative hotel name for response
    hotel_name = (
        final_state["recommendations"][0].loyalty_program
        if final_state["recommendations"]
        else "N/A"
    )

    # Build _debug payload so frontend can animate each agent step
    debug = {
        "valid_cards": [
            {"card_name": c.card_name, "last_four": c.last_four, "points_balance": c.points_balance}
            for c in final_state.get("valid_cards", [])
        ],
        "hotels": [
            {"hotel_name": h.hotel_name, "total_price": h.total_price, "loyalty_program": h.loyalty_program}
            for h in final_state.get("hotels", [])
        ],
        "all_options": [
            {
                "card_name": o["card"].card_name,
                "loyalty_program": o["partner"].partner_name,
                "transfer_ratio": o["partner"].transfer_ratio,
                "dollar_value": o["dollar_value"],
            }
            for o in final_state.get("_raw_options", [])
        ],
    }

    return AgentResponse(
        hotel_name          = hotel_name,
        top_recommendations = final_state["recommendations"],
        agent_summary       = final_state["agent_summary"],
        _debug              = debug,
    )