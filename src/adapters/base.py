from abc import ABC, abstractmethod

from src.schemas.ticket import TicketCreate


class BaseAdapter(ABC):
    """Every helpdesk adapter implements this interface."""

    @abstractmethod
    async def fetch_new_tickets(self) -> list[TicketCreate]:
        """Pull unprocessed tickets from the source system."""
        ...

    @abstractmethod
    async def sync_back(self, ticket_id: str, updates: dict) -> bool:
        """Push classification/response back to the source system."""
        ...

    @abstractmethod
    async def verify_connection(self) -> bool:
        """Health check — can we reach the source system?"""
        ...