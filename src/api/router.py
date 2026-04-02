from fastapi import APIRouter

from src.api.v1 import tickets

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(tickets.router)