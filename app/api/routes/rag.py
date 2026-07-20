from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.rag.rag_engine import rag_engine

router = APIRouter()


class RAGQueryRequest(BaseModel):
    question: str
    user_id: Optional[str] = None
    user_context: Optional[dict] = None


class RAGFollowUpRequest(BaseModel):
    question: str
    recommendations: List[dict]   # serialized AgentRecommendation list


class RAGQueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[str]


@router.post("/ingest")
async def ingest_knowledge_base(force_rebuild: bool = False):
    """
    Build or rebuild the RAG vector store from knowledge base documents.
    Call this once on first setup, or when documents are updated.
    """
    try:
        count = await rag_engine.ingest(force_rebuild=force_rebuild)
        return {
            "status": "success",
            "message": "Vector store built." if count > 0 else "Loaded existing vector store.",
            "chunks_ingested": count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=RAGQueryResponse)
async def query_knowledge_base(request: RAGQueryRequest):
    """
    Ask a natural language question about loyalty points, cards, or hotels.
    Returns a grounded answer from the knowledge base.
    """
    try:
        result = await rag_engine.query(
            question     = request.question,
            user_context = request.user_context,
        )
        return RAGQueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/followup", response_model=RAGQueryResponse)
async def followup_on_recommendations(request: RAGFollowUpRequest):
    """
    Ask a follow-up question in the context of agent recommendations.
    E.g. 'Why is option 1 better than option 3?'
    """
    try:
        from app.models.schemas import AgentRecommendation
        recs = [AgentRecommendation(**r) for r in request.recommendations]
        result = await rag_engine.query_with_recommendation(
            question        = request.question,
            recommendations = recs,
        )
        return RAGQueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))