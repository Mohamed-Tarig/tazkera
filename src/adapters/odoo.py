from src.adapters.base import BaseAdapter
from src.schemas.ticket import TicketCreate


class OdooAdapter(BaseAdapter):
    """
    Odoo Helpdesk adapter — connects via XML-RPC or REST.
    Stub for now. Full implementation in Step 4.
    """

    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url
        self.db = db
        self.username = username
        self.password = password

    async def fetch_new_tickets(self) -> list[TicketCreate]:
        raise NotImplementedError("Odoo adapter coming in Step 4")

    async def sync_back(self, ticket_id: str, updates: dict) -> bool:
        raise NotImplementedError("Odoo adapter coming in Step 4")

    async def verify_connection(self) -> bool:
        raise NotImplementedError("Odoo adapter coming in Step 4")