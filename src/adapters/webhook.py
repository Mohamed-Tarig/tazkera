from src.adapters.base import BaseAdapter
from src.schemas.ticket import TicketCreate


class WebhookAdapter(BaseAdapter):
    """
    Generic webhook adapter — the default.
    Tickets come in via POST request, no polling needed.
    sync_back is a no-op since the caller handles their own state.
    """

    async def fetch_new_tickets(self) -> list[TicketCreate]:
        # Webhook is push-based, not pull-based.
        # Tickets arrive via the /ingest endpoint directly.
        return []

    async def sync_back(self, ticket_id: str, updates: dict) -> bool:
        # No remote system to update — caller manages their own state.
        return True

    async def verify_connection(self) -> bool:
        # Always available — it's just an endpoint.
        return True