from fastapi import APIRouter

from src.api.v1 import tickets
from src.api.v1 import odoo

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(tickets.router)
api_router.include_router(odoo.router)