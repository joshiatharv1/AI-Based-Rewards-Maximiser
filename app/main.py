from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import cards, hotels, booking, conversion, agent, rag, liteapi
from app.core.config import settings

app = FastAPI(
    title="Optivoy Rewards Engine",
    description="Agentic loyalty rewards booking system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards.router,      prefix="/api/cards",      tags=["Credit Cards"])
app.include_router(hotels.router,     prefix="/api/hotels",     tags=["Hotels"])
app.include_router(conversion.router, prefix="/api/conversion", tags=["Points Conversion"])
app.include_router(booking.router,    prefix="/api/booking",    tags=["Booking"])
app.include_router(agent.router,      prefix="/api/agent",      tags=["Agent"])
app.include_router(rag.router,        prefix="/api/rag",        tags=["RAG"])
app.include_router(liteapi.router,     prefix="/api/hotels",     tags=["Hotels"])

@app.get("/")
async def root():
    return {
        "service": "Optivoy Rewards Engine",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "ok"}