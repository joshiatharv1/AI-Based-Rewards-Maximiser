from fastapi import APIRouter, HTTPException
from app.agents.rewards_agent import run_agent
from app.models.schemas import AgentResponse
from pydantic import BaseModel

router = APIRouter()

class AgentRequest(BaseModel):
    user_id:   str
    city_code: str
    check_in:  str
    check_out: str
    adults:    int = 1

@router.post("/recommend", response_model=AgentResponse)
async def get_recommendations(request: AgentRequest):
    """
    Run the full agentic workflow.
    Returns top 3 redemption options ranked by value across all user cards.
    """
    try:
        result = await run_agent(
            user_id   = request.user_id,
            city_code = request.city_code,
            check_in  = request.check_in,
            check_out = request.check_out,
            adults    = request.adults,
        )
        if not result.top_recommendations:
            raise HTTPException(
                status_code=404,
                detail="No redemption options found for your cards and search criteria."
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))