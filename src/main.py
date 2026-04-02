from fastapi import FastAPI

from src.api.router import api_router

app = FastAPI(
    title="Tazkera",
    description="AI Ticket Intelligence Layer",
    version="0.1.0",
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "tazkera"}